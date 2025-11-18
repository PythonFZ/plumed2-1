# /* +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#    Copyright (c) 2011-2025 The plumed team
#    (see the PEOPLE file at the root of the distribution for a list of names)
#
#    See http://www.plumed.org for more information.
#
#    This file is part of plumed, version 2.
#
#    plumed is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    plumed is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with plumed.  If not, see <http://www.gnu.org/licenses/>.
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ */
"""
Custom build hooks for hatchling to compile Cython extensions and bundle PLUMED binaries.
"""

import os
import platform
import shutil
import subprocess
import sysconfig
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.metadata.plugin.interface import MetadataHookInterface


class CustomMetadataHook(MetadataHookInterface):
    """Read version from VERSION.txt file."""

    PLUGIN_NAME = "custom"

    def update(self, metadata: dict) -> None:
        version_file = Path(self.root) / ".." / "VERSION.txt"
        if version_file.exists():
            content = version_file.read_text()
            # Extract version, skipping comment lines
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Convert -dev to .dev0 for PEP 440 compatibility
                    version = line.replace("-dev", ".dev0")
                    metadata["version"] = version
                    break


class CustomBuildHook(BuildHookInterface):
    """Build hook for compiling Cython extensions and bundling PLUMED binaries."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        """Initialize the build process."""
        if self.target_name != "wheel":
            return

        # Build PLUMED from source if not already built
        self._build_plumed()

        # Compile Cython extension
        self._compile_cython_extension()

        # Bundle PLUMED binaries
        self._bundle_binaries(build_data)

        # Set wheel tag to be platform-specific
        build_data["infer_tag"] = True
        build_data["pure_python"] = False

    def _build_plumed(self) -> None:
        """Build PLUMED from source if not already built."""
        root = Path(self.root).resolve()
        plumed_root = (root / "..").resolve()
        install_dir = plumed_root / "bin"

        # Check if already built
        if platform.system() == "Darwin":
            kernel_lib = install_dir / "lib" / "libplumedKernel.dylib"
        else:
            kernel_lib = install_dir / "lib" / "libplumedKernel.so"

        if kernel_lib.exists():
            print(f"PLUMED already built at {install_dir}")
            return

        # Check if we're in the PLUMED source tree
        configure_script = plumed_root / "configure"
        if not configure_script.exists():
            print("WARNING: Not in PLUMED source tree, skipping build")
            print(f"  Expected configure at: {configure_script}")
            return

        print("Building PLUMED from source...")
        print(f"  Source directory: {plumed_root}")
        print(f"  Install directory: {install_dir}")

        # Configure
        configure_cmd = [
            str(configure_script),
            f"--prefix={install_dir}",
            "--disable-doc",
            "--disable-python",  # We're building our own Python interface
        ]

        print(f"Running: {' '.join(configure_cmd)}")
        subprocess.run(configure_cmd, cwd=str(plumed_root), check=True)

        # Build
        import multiprocessing
        num_jobs = multiprocessing.cpu_count()
        print(f"Running: make -j{num_jobs}")
        subprocess.run(["make", f"-j{num_jobs}"], cwd=str(plumed_root), check=True)

        # Install
        print("Running: make install")
        subprocess.run(["make", "install"], cwd=str(plumed_root), check=True)

        print(f"PLUMED built and installed to {install_dir}")

    def _compile_cython_extension(self) -> None:
        """Compile the Cython extension module."""
        import tempfile

        from Cython.Build import cythonize
        from setuptools import Distribution, Extension

        # Paths
        root = Path(self.root)
        plumed_dir = root / "plumed"
        pyx_file = plumed_dir / "_core.pyx"

        if not pyx_file.exists():
            raise FileNotFoundError(f"Cython source file not found: {pyx_file}")

        # Determine include directory
        include_dir = os.environ.get("plumed_include_dir")
        if include_dir:
            include_dirs = [include_dir]
        else:
            # Check for local include first (for sdist builds), then source wrapper, then bin/include
            local_include = root / "include"
            source_wrapper = root / ".." / "src" / "wrapper"
            parent_include = root / ".." / "bin" / "include" / "plumed" / "wrapper"
            if local_include.exists() and (local_include / "Plumed.h").exists():
                include_dirs = [str(local_include)]
            elif source_wrapper.exists():
                include_dirs = [str(source_wrapper)]
            elif parent_include.exists():
                include_dirs = [str(parent_include)]
            else:
                include_dirs = [str(root / "include")]

        # Compile flags
        extra_compile_args = [
            "-D__PLUMED_HAS_DLOPEN",
            "-D__PLUMED_WRAPPER_LINK_RUNTIME=1",
            "-D__PLUMED_WRAPPER_IMPLEMENTATION=1",
            "-D__PLUMED_WRAPPER_EXTERN=0",
        ]

        # Check for default kernel path
        default_kernel = os.environ.get("plumed_default_kernel")
        if default_kernel:
            extra_compile_args.append(f"-D__PLUMED_DEFAULT_KERNEL={os.path.abspath(default_kernel)}")

        # Check for RTLD_DEEPBIND disable
        if os.environ.get("plumed_disable_rtld_deepbind"):
            extra_compile_args.append("-D__PLUMED_WRAPPER_ENABLE_RTLD_DEEPBIND=0")

        # macOS deployment target handling
        if platform.system() == "Darwin":
            if "MACOSX_DEPLOYMENT_TARGET" not in os.environ:
                mac_ver = platform.mac_ver()[0]
                if mac_ver:
                    from packaging.version import Version
                    current_system = Version(mac_ver)
                    python_target = sysconfig.get_config_var("MACOSX_DEPLOYMENT_TARGET")
                    if python_target:
                        if Version(str(python_target)) < Version("10.9") and current_system >= Version("10.9"):
                            os.environ["MACOSX_DEPLOYMENT_TARGET"] = "10.9"

        # Create extension
        ext = Extension(
            name="plumed._core",
            sources=[str(pyx_file)],
            language="c",
            include_dirs=include_dirs,
            extra_compile_args=extra_compile_args,
        )

        # Cythonize
        ext_modules = cythonize([ext], language_level=3)

        # Build using setuptools
        dist = Distribution({"ext_modules": ext_modules})
        dist.package_dir = {"": str(root)}

        # Build in place
        cmd = dist.get_command_obj("build_ext")
        cmd.inplace = True
        cmd.ensure_finalized()
        cmd.run()

        # Move the compiled extension to plumed directory if needed
        # The extension should be built in plumed/ directory

    def _bundle_binaries(self, build_data: dict) -> None:
        """Bundle PLUMED kernel library, executable, and headers."""
        root = Path(self.root)
        plumed_dir = root / "plumed"

        # Create directories for binaries and includes
        lib_dir = plumed_dir / "_lib"
        bin_dir = plumed_dir / "_bin"
        include_dir = plumed_dir / "_include"
        lib_dir.mkdir(exist_ok=True)
        bin_dir.mkdir(exist_ok=True)
        include_dir.mkdir(exist_ok=True)

        # Determine source locations for binaries
        # Check environment variables first, then default locations
        plumed_prefix = os.environ.get("PLUMED_PREFIX")
        if plumed_prefix:
            source_lib_dir = Path(plumed_prefix) / "lib"
            source_bin_dir = Path(plumed_prefix) / "bin"
            source_include_dir = Path(plumed_prefix) / "include" / "plumed"
        else:
            # Default to parent directory's bin
            source_lib_dir = root / ".." / "bin" / "lib"
            source_bin_dir = root / ".." / "bin" / "bin"
            source_include_dir = root / ".." / "bin" / "include" / "plumed"

        # Bundle kernel library
        kernel_bundled = False
        if source_lib_dir.exists():
            if platform.system() == "Darwin":
                kernel_patterns = ["libplumedKernel.dylib"]
            else:
                kernel_patterns = ["libplumedKernel.so"]

            for pattern in kernel_patterns:
                for kernel_file in source_lib_dir.glob(pattern):
                    dest = lib_dir / kernel_file.name
                    shutil.copy2(kernel_file, dest)
                    kernel_bundled = True
                    print(f"Bundled kernel library: {kernel_file.name}")
                    break
                if kernel_bundled:
                    break

        # Bundle plumed executable
        plumed_bundled = False
        if source_bin_dir.exists():
            plumed_exe = source_bin_dir / "plumed"
            if plumed_exe.exists():
                dest = bin_dir / "plumed"
                shutil.copy2(plumed_exe, dest)
                # Ensure executable permission
                dest.chmod(dest.stat().st_mode | 0o111)
                plumed_bundled = True
                print(f"Bundled plumed executable")

        # Bundle Plumed.h header for compilation use
        if source_include_dir.exists():
            header_file = source_include_dir / "wrapper" / "Plumed.h"
            if header_file.exists():
                dest = include_dir / "Plumed.h"
                shutil.copy2(header_file, dest)
                print(f"Bundled Plumed.h header")

        # Add force_include for the bundled files
        if "force_include" not in build_data:
            build_data["force_include"] = {}

        # Include bundled directories
        for subdir in [lib_dir, bin_dir, include_dir]:
            if subdir.exists():
                for item in subdir.iterdir():
                    rel_path = item.relative_to(root)
                    build_data["force_include"][str(item)] = str(rel_path)

        if not kernel_bundled:
            print("WARNING: No PLUMED kernel library found to bundle")
            print(f"  Searched in: {source_lib_dir}")
            print("  Set PLUMED_PREFIX environment variable to specify PLUMED installation")

    def clean(self, versions: list) -> None:
        """Clean up build artifacts."""
        root = Path(self.root)
        plumed_dir = root / "plumed"

        # Remove compiled extensions
        for ext in ["*.so", "*.dylib", "*.pyd"]:
            for f in plumed_dir.glob(ext):
                f.unlink()

        # Remove bundled binaries and includes
        for subdir in ["_lib", "_bin", "_include"]:
            dir_path = plumed_dir / subdir
            if dir_path.exists():
                shutil.rmtree(dir_path)

        # Remove generated C files
        c_file = plumed_dir / "_core.c"
        if c_file.exists():
            c_file.unlink()
