"""Defines the exceptions used by xnat sub-modules"""


class XnatException(Exception):
    """Default exception for xnat errors"""
    study = None
    session = None

    def __repr__(self):
        return 'Study:{} Session:{} Error:{}'.format(self.study,
                                                     self.session,
                                                     self.message)


class DashboardException(Exception):
    """Default exception for dashboard errors"""
