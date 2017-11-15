import os
from core.utils import versioning #@UnresolvedImport


os.chdir("../")
name=raw_input("Choose storage label (default is empty): ")
versioning.store("snapshots",label=name or None)
raw_input("Done")