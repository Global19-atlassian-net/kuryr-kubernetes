# Copyright (c) 2016 Mirantis, Inc.
# All Rights Reserved.
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

import abc
import six

from kuryr.lib._i18n import _LE
from oslo_log import log as logging
from stevedore import driver as stv_driver

from kuryr_kubernetes import config

LOG = logging.getLogger(__name__)

_DRIVER_NAMESPACE_BASE = 'kuryr_kubernetes.controller.drivers'
_DRIVER_MANAGERS = {}


class DriverBase(object):
    """Base class for controller drivers.

    Subclasses must define an *ALIAS* attribute that is used to find a driver
    implementation by `get_instance` class method which utilises
    `stevedore.driver.DriverManager` with the namespace set to
    'kuryr_kubernetes.controller.drivers.*ALIAS*' and the name of
    the driver determined from the '[kubernetes]/*ALIAS*_driver' configuration
    parameter.

    Usage example:

        @six.add_metaclass(abc.ABCMeta)
        class SomeDriverInterface(DriverBase):
            ALIAS = 'driver_alias'

            @abc.abstractmethod
            def some_method(self):
                pass

        driver = SomeDriverInterface.get_instance()
        driver.some_method()
    """

    @classmethod
    def get_instance(cls):
        """Get an implementing driver instance."""

        alias = cls.ALIAS

        try:
            manager = _DRIVER_MANAGERS[alias]
        except KeyError:
            name = config.CONF.kubernetes[alias + '_driver']
            manager = stv_driver.DriverManager(
                namespace="%s.%s" % (_DRIVER_NAMESPACE_BASE, alias),
                name=name,
                invoke_on_load=True)
            _DRIVER_MANAGERS[alias] = manager

        driver = manager.driver
        if not isinstance(driver, cls):
            raise TypeError(_LE("Invalid %(alias)r driver type: %(driver)s, "
                                "must be a subclass of %(type)s") % {
                'alias': alias,
                'driver': driver.__class__.__name__,
                'type': cls})
        return driver


@six.add_metaclass(abc.ABCMeta)
class PodProjectDriver(DriverBase):
    """Provides an OpenStack project ID for Kubernetes Pod ports."""

    ALIAS = 'pod_project'

    @abc.abstractmethod
    def get_project(self, pod):
        """Get an OpenStack project ID for Kubernetes Pod ports.

        :param pod: dict containing Kubernetes Pod object
        :return: project ID
        """

        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class ServiceProjectDriver(DriverBase):
    """Provides an OpenStack project ID for Kubernetes Services."""

    ALIAS = 'service_project'

    @abc.abstractmethod
    def get_project(self, service):
        """Get an OpenStack project ID for Kubernetes Service.

        :param service: dict containing Kubernetes Service object
        :return: project ID
        """

        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class PodSubnetsDriver(DriverBase):
    """Provides subnets for Kubernetes Pods."""

    ALIAS = 'pod_subnets'

    @abc.abstractmethod
    def get_subnets(self, pod, project_id):
        """Get subnets for Pod.

        :param pod: dict containing Kubernetes Pod object
        :param project_id: OpenStack project ID
        :return: dict containing the mapping 'subnet_id' -> 'network' for all
                 the subnets we want to create ports on, where 'network' is an
                 `os_vif.network.Network` object containing a single
                 `os_vif.subnet.Subnet` object corresponding to the 'subnet_id'
        """
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class ServiceSubnetsDriver(DriverBase):
    """Provides subnets for Kubernetes Services."""

    ALIAS = 'service_subnets'

    @abc.abstractmethod
    def get_subnets(self, service, project_id):
        """Get subnets for Service.

        :param service: dict containing Kubernetes Pod object
        :param project_id: OpenStack project ID
        :return: dict containing the mapping 'subnet_id' -> 'network' for all
                 the subnets we want to create ports on, where 'network' is an
                 `os_vif.network.Network` object containing a single
                 `os_vif.subnet.Subnet` object corresponding to the 'subnet_id'
        """
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class PodSecurityGroupsDriver(DriverBase):
    """Provides security groups for Kubernetes Pods."""

    ALIAS = 'pod_security_groups'

    @abc.abstractmethod
    def get_security_groups(self, pod, project_id):
        """Get a list of security groups' IDs for Pod.

        :param pod: dict containing Kubernetes Pod object
        :param project_id: OpenStack project ID
        :return: list containing security groups' IDs
        """
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class ServiceSecurityGroupsDriver(DriverBase):
    """Provides security groups for Kubernetes Services."""

    ALIAS = 'service_security_groups'

    @abc.abstractmethod
    def get_security_groups(self, service, project_id):
        """Get a list of security groups' IDs for Service.

        :param service: dict containing Kubernetes Service object
        :param project_id: OpenStack project ID
        :return: list containing security groups' IDs
        """
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class PodVIFDriver(DriverBase):
    """Manages Neutron ports to provide VIFs for Kubernetes Pods."""

    ALIAS = 'pod_vif'

    @abc.abstractmethod
    def request_vif(self, pod, project_id, subnets, security_groups):
        """Links Neutron port to pod and returns it as VIF object.

        Implementing drivers must ensure the Neutron port satisfying the
        requested parameters is present and is valid for specified `pod`. It
        is up to the implementing drivers to either create new ports on each
        request or reuse available ports when possible.

        Implementing drivers may return a VIF object with its `active` field
        set to 'False' to indicate that Neutron port requires additional
        actions to enable network connectivity after VIF is plugged (e.g.
        setting up OpenFlow and/or iptables rules by OpenVSwitch agent). In
        that case the Controller will call driver's `activate_vif` method
        and the CNI plugin will block until it receives activation
        confirmation from the Controller.

        :param pod: dict containing Kubernetes Pod object
        :param project_id: OpenStack project ID
        :param subnets: dict containing subnet mapping as returned by
                        `PodSubnetsDriver.get_subnets`. If multiple entries
                        are present in that mapping, it is guaranteed that
                        all entries have the same value of `Network.id`.
        :param security_groups: list containing security groups' IDs as
                                returned by
                                `PodSecurityGroupsDriver.get_security_groups`
        :return: VIF object
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def release_vif(self, pod, vif):
        """Unlinks Neutron port corresponding to VIF object from pod.

        Implementing drivers must ensure the port is either deleted or made
        available for reuse by `PodVIFDriver.request_vif`.

        :param pod: dict containing Kubernetes Pod object
        :param vif: VIF object as returned by `PodVIFDriver.request_vif`
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def activate_vif(self, pod, vif):
        """Updates VIF to become active.

        Implementing drivers should update the specified `vif` object's
        `active` field to 'True' but must ensure that the corresponding
        Neutron port is fully configured (i.e. the container using the `vif`
        can access the requested network resources).

        Implementing drivers may raise `ResourceNotReady` exception to
        indicate that port activation should be retried later which will
        cause `activate_vif` to be called again with the same arguments.

        This method may be called before, after or while the VIF is being
        plugged by the CNI plugin.

        :param pod: dict containing Kubernetes Pod object
        :param vif: VIF object as returned by `PodVIFDriver.request_vif`
        """
        raise NotImplementedError()
