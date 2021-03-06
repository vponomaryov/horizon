# Copyright 2014 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import tabs

from openstack_dashboard.api import manila
from openstack_dashboard.api import neutron

from openstack_dashboard.dashboards.admin.\
    shares.tables import SharesTable
from openstack_dashboard.dashboards.admin.\
    shares.tables import SnapshotsTable
from openstack_dashboard.dashboards.admin.\
    shares.tables import SecurityServiceTable
from openstack_dashboard.dashboards.admin.\
    shares.tables import ShareNetworkTable
from openstack_dashboard.dashboards.admin.\
    shares.tables import ShareServerTable
from openstack_dashboard.dashboards.admin.\
    shares.tables import ShareTypesTable
from openstack_dashboard.dashboards.admin.shares import utils


class SnapshotsTab(tabs.TableTab):
    table_classes = (SnapshotsTable, )
    name = _("Snapshots")
    slug = "snapshots_tab"
    template_name = "horizon/common/_detail_table.html"

    def _set_id_if_nameless(self, snapshots):
        for snap in snapshots:
            if not snap.name:
                snap.name = snap.id

    def get_snapshots_data(self):
        try:
            snapshots = manila.share_snapshot_list(self.request)
            shares = manila.share_list(self.request)
            share_names = dict([(share.id, share.name or share.id)
                                for share in shares])
            for snapshot in snapshots:
                snapshot.share = share_names.get(snapshot.share_id)
        except Exception:
            msg = _("Unable to retrieve snapshot list.")
            exceptions.handle(self.request, msg)
            return []
        #Gather our tenants to correlate against IDs
        utils.set_tenant_name_to_objects(self.request, snapshots)
        return snapshots


class SharesTab(tabs.TableTab):
    table_classes = (SharesTable, )
    name = _("Shares")
    slug = "shares_tab"
    template_name = "horizon/common/_detail_table.html"

    def get_shares_data(self):
        try:
            shares = manila.share_list(self.request,
                                       search_opts={'all_tenants': True})
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve share list.'))
            return []
        #Gather our tenants to correlate against IDs
        utils.set_tenant_name_to_objects(self.request, shares)
        return shares


class ShareTypesTab(tabs.TableTab):
    table_classes = (ShareTypesTable, )
    name = _("Share Types")
    slug = "share_types_tab"
    template_name = "horizon/common/_detail_table.html"

    def get_share_types_data(self):
        try:
            share_types = manila.share_type_list(self.request)
        except Exception:
            share_types = []
            exceptions.handle(self.request,
                              _("Unable to retrieve share types"))
        # Convert dict with extra specs to friendly view
        for st in share_types:
            es_str = ""
            for k, v in st.extra_specs.iteritems():
                es_str += "%s=%s\r\n<br />" % (k, v)
            st.extra_specs = mark_safe(es_str)
        return share_types


class SecurityServiceTab(tabs.TableTab):
    table_classes = (SecurityServiceTable,)
    name = _("Security Services")
    slug = "security_services_tab"
    template_name = "horizon/common/_detail_table.html"

    def get_security_services_data(self):
        try:
            security_services = manila.security_service_list(
                self.request, search_opts={'all_tenants': True})
        except Exception:
            security_services = []
            exceptions.handle(self.request,
                              _("Unable to retrieve security services"))

        utils.set_tenant_name_to_objects(self.request, security_services)
        return security_services


class ShareNetworkTab(tabs.TableTab):
    table_classes = (ShareNetworkTable,)
    name = _("Share Networks")
    slug = "share_networks_tab"
    template_name = "horizon/common/_detail_table.html"

    def get_share_networks_data(self):
        try:
            share_networks = manila.share_network_list(
                self.request, detailed=True, search_opts={'all_tenants': True})
            neutron_net_names = dict([(net.id, net.name) for net in
                                      neutron.network_list(self.request)])
            neutron_subnet_names = dict([(net.id, net.name) for net in
                                      neutron.subnet_list(self.request)])
            for share in share_networks:
                share.neutron_net = neutron_net_names.get(
                    share.neutron_net_id) or share.neutron_net_id
                share.neutron_subnet = neutron_subnet_names.get(
                    share.neutron_subnet_id) or share.neutron_net_id
        except Exception:
            share_networks = []
            exceptions.handle(self.request,
                              _("Unable to retrieve share networks"))
        utils.set_tenant_name_to_objects(self.request, share_networks)
        return share_networks


class ShareServerTab(tabs.TableTab):
    table_classes = (ShareServerTable,)
    name = _("Share Servers")
    slug = "share_servers_tab"
    template_name = "horizon/common/_detail_table.html"

    def get_share_servers_data(self):
        try:
            share_servers = manila.share_server_list(
                self.request)
        except Exception:
            share_servers = []
            exceptions.handle(self.request,
                              _("Unable to retrieve share servers"))
        utils.set_tenant_name_to_objects(self.request, share_servers)
        return share_servers


class ShareServerOverviewTab(tabs.Tab):
    name = _("Overview")
    slug = "overview"
    template_name = ("admin/shares/_detail_share_server.html")

    def get_context_data(self, request):
        return {"share_server": self.tab_group.kwargs['share_server']}


class ShareServerDetailTabs(tabs.TabGroup):
    slug = "share_server_details"
    tabs = (ShareServerOverviewTab,)


class ShareTabs(tabs.TabGroup):
    slug = "share_tabs"
    tabs = (SharesTab, SnapshotsTab, ShareNetworkTab, SecurityServiceTab,
            ShareTypesTab, ShareServerTab)
    sticky = True


class SnapshotOverviewTab(tabs.Tab):
    name = _("Snapshot Overview")
    slug = "snapshot_overview_tab"
    template_name = ("admin/shares/"
                     "_snapshot_detail_overview.html")

    def get_context_data(self, request):
        return {"snapshot": self.tab_group.kwargs['snapshot']}


class SnapshotDetailTabs(tabs.TabGroup):
    slug = "snapshot_details"
    tabs = (SnapshotOverviewTab,)
