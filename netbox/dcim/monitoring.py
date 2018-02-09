from __future__ import unicode_literals

import importlib
import inspect
import pkgutil

from django.conf import settings

from .constants import LOG_DEFAULT, LOG_FAILURE, LOG_INFO, LOG_OK, LOG_WARNING, LOG_COLORS, LOG_DESCRIPTIONS


def get_monitoring():
    """
    Compile a list of all interfaces available across all modules in the monitoring path. Returns a list of modules:

    [
        module_name,
        module_name,
        ...
    ]
    """
    module_list = []

    # Iterate through all modules within the monitoring path. These are the user-created files in which monitoring interfaces are
    # defined.
    for importer, module_name, is_pkg in pkgutil.walk_packages([settings.MONITORING_ROOT]):
        module = importlib.import_module('monitoring.{}'.format(module_name))

        module_list += [cls() for _, cls in inspect.getmembers(module, is_monitoring)]

    return module_list


def get(device):
    modules = get_monitoring()

    results = MonitoringResults()

    for module in modules:
        results += module.run(device)

    return results


def is_monitoring(obj):
    """
    Returns True if the given object is a monitoring module.
    """
    if obj in Monitoring.__subclasses__():
        return True
    return False


class Monitoring(object):
    """
    NetBox users can extend this object to write custom methods to be used for fetching device statuses within NetBox. Each
    module must have one method named `get`.
    """
    description = None

    def __init__(self):

        self.active_test = None
        self.failed = False

        # Compile test methods and initialize results skeleton
        self._results = MonitoringResults()

    @property
    def module(self):
        return self.__module__.rsplit('.', 1)[1]

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def full_name(self):
        return '.'.join([self.module, self.name])

    def get(self, device):
        raise NotImplementedError()

    def log_default(self, message=""):
        """
        Log a message which is not associated with a particular object.
        """
        self._results.log(LOG_DEFAULT, message)

    def log_ok(self, message=""):
        """
        Record a successful test against an object. Logging a message is optional.
        """
        self._results.log(LOG_OK, message)

    def log_info(self, message):
        """
        Log an informational message.
        """
        self._results.log(LOG_INFO, message)

    def log_warning(self, message):
        """
        Log a warning.
        """
        self._results.log(LOG_WARNING, message)

    def log_failure(self, message):
        """
        Log a failure. Calling this method will automatically mark the report as failed.
        """
        self._results.log(LOG_FAILURE, message)

    def run(self, device):
        """
        Run the report and return its results. Each test method will be executed in order.
        """
        self.get(device)

        return self._results


class MonitoringResults(object):
    def __init__(self):
        self.logs = {
            LOG_DEFAULT: [],
            LOG_OK: [],
            LOG_INFO: [],
            LOG_WARNING: [],
            LOG_FAILURE: []
        }

    def log(self, level, message):
        self.logs[level].append(message)

    def get_worst_message(self):
        if self.logs[LOG_FAILURE]:
            return MonitoringMessage(LOG_FAILURE, self.logs[LOG_FAILURE][0])
        if self.logs[LOG_WARNING]:
            return MonitoringMessage(LOG_WARNING, self.logs[LOG_WARNING][0])
        if self.logs[LOG_INFO]:
            return MonitoringMessage(LOG_INFO, self.logs[LOG_INFO][0])
        if self.logs[LOG_OK]:
            return MonitoringMessage(LOG_OK, self.logs[LOG_OK][0])
        if self.logs[LOG_DEFAULT]:
            return MonitoringMessage(LOG_DEFAULT, self.logs[LOG_DEFAULT][0])
        return MonitoringMessage(LOG_DEFAULT, "")

    def __add__(self, other):
        if other == 0:
            return self
        if not isinstance(other, MonitoringResults):
            raise ValueError()

        for key in other.logs:
            if key in self.logs:
                self.logs[key] += other.logs[key]
            else:
                self.logs[key] = other.logs[key]

        return self

    def get_messages(self, level):
        return self.logs[level]

    def get_all_messages(self):
        output = []
        for level in self.logs:
            for message in self.logs[level]:
                output.append(MonitoringMessage(level, message))

        output.sort(key=lambda m: m.level, reverse=True)
        return output


class MonitoringMessage(object):
    def __init__(self, level, message):
        self.level = level
        self.message = message

    @property
    def color(self):
        return LOG_COLORS[self.level]

    @property
    def description(self):
        return LOG_DESCRIPTIONS[self.level]
