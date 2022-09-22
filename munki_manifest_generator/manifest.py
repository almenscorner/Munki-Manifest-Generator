class Manifest:
    def __init__(self, catalogs, included_manifests, display_name, serialnumber, user):
        """Used to create a manifest object."""
        self.catalogs = catalogs
        self.included_manifests = included_manifests
        self.managed_installs = []
        self.optional_installs = []
        self.display_name = display_name
        self.serialnumber = serialnumber
        self.user = user
