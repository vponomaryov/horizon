# Copyright (c) 2014 NetApp, Inc.
# All rights reserved.

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

"""
Views for managing shares.
"""

from django.core.urlresolvers import reverse
from django.forms import ValidationError  # noqa
from django.template.defaultfilters import filesizeformat  # noqa
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon.utils import fields
from horizon.utils.memoized import memoized  # noqa

from openstack_dashboard.api import manila
#from openstack_dashboard.usage import quotas


class CreateForm(forms.SelfHandlingForm):
    name = forms.CharField(max_length="255", label=_("Share Name"))
    description = forms.CharField(widget=forms.Textarea,
                                  label=_("Description"), required=False)
    type = forms.ChoiceField(label=_("Type"),
                             required=False)
    size = forms.IntegerField(min_value=1, label=_("Size (GB)"))
    share_network = forms.ChoiceField(label=_("Share Network"),
                                      required=False)
    share_source_type = forms.ChoiceField(label=_("Share Source"),
                                          required=False,
                                          widget=forms.Select(attrs={
                                              'class': 'switchable',
                                              'data-slug': 'source'}))
    snapshot_source = forms.ChoiceField(
        label=_("Use snapshot as a source"),
        widget=fields.SelectWidget(
            attrs={'class': 'snapshot-selector'},
            data_attrs=('size', 'name'),
            transform=lambda x: "%s (%sGB)" % (x.name, x.size)),
        required=False)

    def __init__(self, request, *args, **kwargs):
        super(CreateForm, self).__init__(request, *args, **kwargs)
        share_types = ('NFS', 'CIFS')
        share_networks = manila.share_network_list(request)
        self.fields['type'].choices = [(type, type)
                                       for type in share_types]
        self.fields['share_network'].choices = \
            [("", "")] + [(net.id, net.name or net.id) for net in
                          share_networks if net.status == "ACTIVE"]

        if "snapshot_id" in request.GET:
            try:
                snapshot = self.get_snapshot(request,
                                             request.GET["snapshot_id"])
                self.fields['name'].initial = snapshot.name
                self.fields['size'].initial = snapshot.size
                self.fields['snapshot_source'].choices = ((snapshot.id,
                                                           snapshot),)
                try:
                    # Set the share type from the original share
                    orig_share = manila.share_get(request,
                                                    snapshot.share_id)
                    self.fields['type'].initial = orig_share.share_type
                except Exception:
                    pass
                self.fields['size'].help_text = _('Share size must be equal '
                            'to or greater than the snapshot size (%sGB)') \
                            % snapshot.size
                del self.fields['share_source_type']
            except Exception:
                exceptions.handle(request,
                                  _('Unable to load the specified snapshot.'))
        else:
            source_type_choices = []

            try:
                snapshot_list = manila.share_snapshot_list(request)
                snapshots = [s for s in snapshot_list
                              if s.status == 'available']
                if snapshots:
                    source_type_choices.append(("snapshot_source",
                                                _("Snapshot")))
                    choices = [('', _("Choose a snapshot"))] + \
                              [(s.id, s) for s in snapshots]
                    self.fields['snapshot_source'].choices = choices
                else:
                    del self.fields['snapshot_source']
            except Exception:
                exceptions.handle(request, _("Unable to retrieve "
                        "share snapshots."))

            if source_type_choices:
                choices = ([('no_source_type',
                             _("No source, empty share"))] +
                            source_type_choices)
                self.fields['share_source_type'].choices = choices
            else:
                del self.fields['share_source_type']

    def handle(self, request, data):
        try:
            #usages = quotas.tenant_limit_usages(self.request)
            #availableGB = usages['maxTotalShareGigabytes'] - \
            #    usages['gigabytesUsed']
            #availableVol = usages['maxTotalShares'] - usages['sharesUsed']

            snapshot_id = None
            source_type = data.get('share_source_type', None)
            share_network = data.get('share_network', None)
            if (data.get("snapshot_source", None) and
                  source_type in [None, 'snapshot_source']):
                # Create from Snapshot
                snapshot = self.get_snapshot(request,
                                             data["snapshot_source"])
                snapshot_id = snapshot.id
                if (data['size'] < snapshot.size):
                    error_message = _('The share size cannot be less than '
                        'the snapshot size (%sGB)') % snapshot.size
                    raise ValidationError(error_message)
            else:
                if type(data['size']) is str:
                    data['size'] = int(data['size'])
            #
            #if availableGB < data['size']:
            #    error_message = _('A share of %(req)iGB cannot be created as '
            #                      'you only have %(avail)iGB of your quota '
            #                      'available.')
            #    params = {'req': data['size'],
            #              'avail': availableGB}
            #    raise ValidationError(error_message % params)
            #elif availableVol <= 0:
            #    error_message = _('You are already using all of your '
            #                      'available'
            #                      ' shares.')
            #    raise ValidationError(error_message)

            metadata = {}

            share = manila.share_create(request,
                                        data['size'],
                                        data['name'],
                                        data['description'],
                                        data['type'],
                                        share_network_id=share_network,
                                        snapshot_id=snapshot_id,
                                        metadata=metadata)
            message = _('Creating share "%s"') % data['name']
            messages.info(request, message)
            return share
        except ValidationError as e:
            self.api_error(e.messages[0])
            return False
        except Exception:
            exceptions.handle(request, ignore=True)
            self.api_error(_("Unable to create share."))
            return False

    @memoized
    def get_snapshot(self, request, id):
        return manila.share_snapshot_get(request, id)


class UpdateForm(forms.SelfHandlingForm):
    name = forms.CharField(max_length="255", label=_("Share Name"))
    description = forms.CharField(widget=forms.Textarea,
                                  label=_("Description"), required=False)

    def handle(self, request, data):
        share_id = self.initial['share_id']
        try:
            share = manila.share_get(self.request, share_id)
            manila.share_update(request, share, data['name'],
                                data['description'])
            message = _('Updating share "%s"') % data['name']
            messages.success(request, message)
            return True
        except Exception:
            redirect = reverse("horizon:project:shares:index")
            exceptions.handle(request,
                              _('Unable to update share.'),
                              redirect=redirect)


class AddRule(forms.SelfHandlingForm):
    access_to = forms.CharField(label=_("Access To"), max_length="255",
                                required=True)
    type = forms.ChoiceField(label=_("Type"),
                             required=True,
                             choices=(('ip', 'ip'), ('sid', 'sid')))

    def handle(self, request, data):
        share_id = self.initial['share_id']
        try:
            manila.share_allow(request, share_id, access=data['access_to'],
                               access_type=data['type'])
        except Exception:
            redirect = reverse("horizon:project:shares:index")
            exceptions.handle(request,
                              _('Unable to add rule.'),
                              redirect=redirect)
