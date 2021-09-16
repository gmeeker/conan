import copy
import os
import shutil

from conans import tools
from conans.client.file_copier import FileCopier

class ConanMiddleware(object):
    """ The base class for all middleware
    """

    def __init__(self, conanfile_or_middleware, localattrs=()):
        super().__setattr__("_localattrs", ["_localattrs", "conanfile"] + list(localattrs))
        self.conanfile = conanfile_or_middleware
        print("Applying middleware to " + self.conanfile.display_name)

    def get_conanfile(self):
        result = self.conanfile
        while result and isinstance(result, ConanMiddleware):
            result = result.conanfile
        return result

    def __getattr__(self, name):
        return getattr(self.conanfile, name)

    def __setattr__(self, name, value):
        if name in self._localattrs:
            super().__setattr__(name, value)
        else:
            setattr(self.conanfile, name, value)

    def __delattr__(self, name, value):
        if name in self._localattrs:
            super().__delattr__(name, value)
        else:
            delattr(self.conanfile, name, value)

    def __eq__(self, other):
        return self.conanfile == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.conanfile)

    def __repr__(self):
        return repr(self.conanfile)

    def __iter__(self):
        yield self

_variants_folder = "variants"

class ConanVariantsMiddleware(ConanMiddleware):
    """ The base class for all middleware with variant builds
    """

    variants_folder = _variants_folder

    def __init__(self, conanfile_or_middleware, variants=None, localattrs=()):
        super().__init__(conanfile_or_middleware, localattrs=list(localattrs)+["_variants"])
        self.set_variants(variants)

    def __iter__(self):
        variants = self.valid() and self.variants()
        if not variants:
            yield self
        else:
            for v in variants:
                conanfile = self.conanfile_variant(v)
                yield conanfile

    def clone(self):
        result = copy.copy(self)
        result.conanfile = result.conanfile.clone()
        return result

    def set_variants(self, variants):
        if not variants:
            self._variants = []
            return
        elif isinstance(variants, (list, tuple)):
            if hasattr(variants[0], "items"):
                self._variants = variants
                return
            v = variants
        else:
            v = str(variants).split();
        self._variants = [{ "arch": arch, "display_name": arch } for arch in v]

    @staticmethod
    def get_variant_folder(basename, variant):
        folder = variant["display_name"]
        if basename:
            return os.path.join(basename, _variants_folder, folder)
        return folder

    def conanfile_variant(self, variant):
        conanfile = self.conanfile.clone()
        display_name = variant.get("display_name", None)
        if display_name:
            conanfile.display_name = "%s[%s]" % (conanfile.display_name, display_name)
        for k, v in variant.items():
            if k != "display_name":
                setattr(conanfile.settings, k, v)
        if not getattr(conanfile, "no_copy_source", False):
            conanfile.source_folder = self.get_variant_folder(self.source_folder, variant)
        conanfile.build_folder = self.get_variant_folder(self.build_folder, variant)
        conanfile.install_folder = conanfile.build_folder
        conanfile.package_folder = self.get_variant_folder(self.package_folder, variant)
        return conanfile

    def valid(self):
        return True

    def variants(self):
        return self._variants

    def copy_source(self, target_conanfile):
        build_folder = self.build_folder
        if build_folder != target_conanfile.build_folder:
            def ignore_variants(path, files):
                if path == build_folder:
                    if _variants_folder in files:
                        return [_variants_folder]
                return [] # ignore nothing
            shutil.copytree(self.build_folder,
                            target_conanfile.build_folder,
                            symlinks=True,
                            ignore=ignore_variants)

    def system_requirements(self):
        """ This must be defined for installer.py so type(conanfile).system_requirements exists. """
        return self.conanfile.system_requirements()

    def package_variants(self):
        variants = self.valid() and self.variants()
        if not variants:
            return self.conanfile.package()
        for v in variants:
            conanfile = self.conanfile_variant(v)
            folders = [conanfile.source_folder, conanfile.build_folder]
            conanfile.copy = FileCopier(folders, conanfile.package_folder)
            with tools.chdir(conanfile.build_folder):
                conanfile.output.info("packaging variant: %s" % v["display_name"])
                conanfile.package()

    def package(self):
        return self.package_variants()

    def test(self):
        variants = self.valid() and self.variants()
        if not variants:
            return self.conanfile.test()
        for v in variants:
            conanfile = self.conanfile_variant(v)
            with tools.chdir(conanfile.build_folder):
                conanfile.test()

    def test(self):
        return self.test_variants()

    def package_id_variants(self):
        variants = self.valid() and self.variants()
        if not variants:
            return self.conanfile.package_id()
        for k in variants[0].keys():
            if k != "display_name":
                setattr(self.info_build.settings, k, ' '.join([str(v[k]) for v in variants]))

    def package_id(self):
        return self.conanfile.package_id()
