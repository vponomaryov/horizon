# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from django.core.urlresolvers import reverse
from django.template.defaultfilters import title  # noqa
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import tables
from openstack_dashboard.api import manila
from openstack_dashboard.api import neutron
from openstack_dashboard.dashboards.project.shares.shares \
    import tables as shares_tables
from openstack_dashboard.dashboards.project.shares.snapshots \
    import tables as snapshot_tables

DELETABLE_STATES = ("available", "error")


def get_size(share):
    return _("%sGB") % share.size


class CreateVolumeType(tables.LinkAction):
    name = "create"
    verbose_name = _("Create Volume Type")
    url = "horizon:admin:shares:create_type"
    classes = ("ajax-modal", "btn-create")
    policy_rules = (("share", "share_extension:types_manage"),)


class DeleteVolumeType(tables.DeleteAction):
    data_type_singular = _("Volume Type")
    data_type_plural = _("Volume Types")
    policy_rules = (("share", "share_extension:types_manage"),)

    def delete(self, request, obj_id):
        manila.volume_type_delete(request, obj_id)


class UpdateVolumeType(tables.LinkAction):
    name = "update volume type"
    verbose_name = _("Update Volume Type")
    url = "horizon:admin:shares:update_type"
    classes = ("ajax-modal", "btn-create")
    policy_rules = (("share", "share_extension:types_manage"),)

    def get_policy_target(self, request, datum=None):
        project_id = None
        if datum:
            project_id = getattr(datum, "os-share-tenant-attr:tenant_id", None)
        return {"project_id": project_id}


class VolumeTypesFilterAction(tables.FilterAction):

    def filter(self, table, volume_types, filter_string):
        """Naive case-insensitive search."""
        q = filter_string.lower()
        return [vt for vt in volume_types if q in vt.name.lower()]


class VolumeTypesTable(tables.DataTable):
    name = tables.Column("name", verbose_name=_("Name"))
    extra_specs = tables.Column("extra_specs", verbose_name=_("Extra specs"), )

    def get_object_display(self, vol_type):
        return vol_type.name

    def get_object_id(self, vol_type):
        return str(vol_type.id)

    class Meta:
        name = "volume_types"
        verbose_name = _("Volume Types")
        table_actions = (CreateVolumeType, DeleteVolumeType,
                         VolumeTypesFilterAction, )
        row_actions = (UpdateVolumeType, DeleteVolumeType, )


class SharesFilterAction(tables.FilterAction):

    def filter(self, table, shares, filter_string):
        """Naive case-insensitive search."""
        q = filter_string.lower()
        return [share for share in shares
                if q in share.name.lower()]


class SharesTable(shares_tables.SharesTable):
    name = tables.Column("name",
                         verbose_name=_("Name"),
                         link="horizon:admin:shares:detail")
    host = tables.Column("host", verbose_name=_("Host"))
    tenant = tables.Column("tenant_name", verbose_name=_("Project"))

    class Meta:
        name = "shares"
        verbose_name = _("Shares")
        status_columns = ["status"]
        row_class = shares_tables.UpdateRow
        table_actions = (shares_tables.DeleteShare, SharesFilterAction)
        row_actions = (shares_tables.DeleteShare,)
        columns = ('tenant', 'host', 'name', 'size', 'status', 'volume_type',
                   'protocol',)


class SnapshotShareNameColumn(tables.Column):
    def get_link_url(self, snapshot):
        return reverse(self.link, args=(snapshot.share_id,))


class DeleteSnapshot(tables.DeleteAction):
    data_type_singular = _("Snapshot")
    data_type_plural = _("Snapshots")
    action_past = _("Scheduled deletion of %(data_type)s")
    policy_rules = (("snapshot", "snapshot:delete"),)

    def get_policy_target(self, request, datum=None):
        project_id = None
        if datum:
            project_id = getattr(datum, "project_id", None)
        return {"project_id": project_id}

    def delete(self, request, obj_id):
        obj = self.table.get_object_by_id(obj_id)
        name = self.table.get_object_display(obj)
        try:
            manila.share_snapshot_delete(request, obj_id)
        except Exception:
            msg = _('Unable to delete snapshot "%s". One or more shares '
                    'depend on it.')
            exceptions.check_message(["snapshots", "dependent"], msg % name)
            raise

    def allowed(self, request, snapshot=None):
        if snapshot:
            return snapshot.status in DELETABLE_STATES
        return True


class SnapshotsTable(tables.DataTable):
    STATUS_CHOICES = (
        ("in-use", True),
        ("available", True),
        ("creating", None),
        ("error", False),
    )
    name = tables.Column("name",
                         verbose_name=_("Name"),
                         link="horizon:admin:shares:snapshot-detail")
    description = tables.Column("description",
                                verbose_name=_("Description"),
                                truncate=40)
    size = tables.Column(get_size,
                         verbose_name=_("Size"),
                         attrs={'data-type': 'size'})
    status = tables.Column("status",
                           filters=(title,),
                           verbose_name=_("Status"),
                           status=True,
                           status_choices=STATUS_CHOICES)
    source = SnapshotShareNameColumn("share",
                                     verbose_name=_("Source"),
                                     link="horizon:admin:shares:detail")

    def get_object_display(self, obj):
        return obj.name

    class Meta:
        name = "snapshots"
        verbose_name = _("Snapshots")
        status_columns = ["status"]
        row_class = snapshot_tables.UpdateRow
        table_actions = (DeleteSnapshot, )
        row_actions = (DeleteSnapshot, )


class DeleteSecurityService(tables.DeleteAction):
    data_type_singular = _("Security Service")
    data_type_plural = _("Security Services")
    policy_rules = (("share", "security_service:delete"),)

    def delete(self, request, obj_id):
        manila.security_service_delete(request, obj_id)


class DeleteShareNetwork(tables.DeleteAction):
    data_type_singular = _("Share Network")
    data_type_plural = _("Share Networks")
    policy_rules = (("share", "share_network:delete"),)

    def delete(self, request, obj_id):
        manila.share_network_delete(request, obj_id)

    def allowed(self, request, obj):
        if obj:
            # NOTE: set always True until statuses become used
            #return obj.status in ["INACTIVE", "ERROR"]
            return True
        return True


class SecurityServiceTable(tables.DataTable):
    name = tables.Column("name",
                         verbose_name=_("Name"),
                         link="horizon:admin:shares:security_service_detail")
    tenant = tables.Column("tenant_name", verbose_name=_("Project"))
    dns_ip = tables.Column("dns_ip", verbose_name=_("DNS IP"))
    server = tables.Column("server", verbose_name=_("Server"))
    domain = tables.Column("domain", verbose_name=_("Domain"))
    user = tables.Column("user", verbose_name=_("Sid"))

    def get_object_display(self, security_service):
        return security_service.name

    def get_object_id(self, security_service):
        return str(security_service.id)

    class Meta:
        name = "security_services"
        verbose_name = _("Security Services")
        table_actions = (DeleteSecurityService,)
        row_actions = (DeleteSecurityService,)


class UpdateShareNetworkRow(tables.Row):
    ajax = True

    def get_data(self, request, share_net_id):
        share_net = manila.share_network_get(request, share_net_id)
        share_net.neutron_net = neutron.network_get(
            request, share_net.neutron_net_id).name_or_id
        share_net.neutron_subnet = neutron.subnet_get(
            request, share_net.neutron_subnet_id).name_or_id
        return share_net


class ShareNetworkTable(tables.DataTable):
    name = tables.Column("name",
                         verbose_name=_("Name"),
                         link="horizon:admin:shares:share_network_detail")
    tenant = tables.Column("tenant_name", verbose_name=_("Project"))
    ip_version = tables.Column("ip_version", verbose_name=_("IP Version"))
    network_type = tables.Column("network_type",
                                 verbose_name=_("Network Type"))
    neutron_net_id = tables.Column("neutron_net",
                                   verbose_name=_("Neutron Net"))
    neutron_subnet_id = tables.Column("neutron_subnet",
                                   verbose_name=_("Neutron Subnet"))
    segmentation_id = tables.Column("segmentation_id",
                                    verbose_name=_("Segmentation Id"))
    # NOTE: removed statuses until it become used
    #status = tables.Column("status", verbose_name=_("Status"))

    def get_object_display(self, share_network):
        return share_network.name or str(share_network.id)

    def get_object_id(self, share_network):
        return str(share_network.id)

    class Meta:
        name = "share_networks"
        verbose_name = _("Share Networks")
        table_actions = (DeleteShareNetwork, )
        row_class = UpdateShareNetworkRow
        row_actions = (DeleteShareNetwork, )