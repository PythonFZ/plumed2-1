# /* +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#    Copyright (c) 2011-2016 The plumed team
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
Python interface to PLUMED.

This package provides a Python wrapper for the PLUMED library, enabling
enhanced sampling methods and collective variable analysis in molecular
dynamics simulations.

Example usage:
    >>> import plumed
    >>> p = plumed.Plumed()
    >>> p.cmd("init")

If the bundled PLUMED kernel is available, it will be used automatically.
Otherwise, set the PLUMED_KERNEL environment variable to point to your
libplumedKernel.so or libplumedKernel.dylib file.
"""

import os
import platform
from pathlib import Path

# Import all public symbols from the compiled extension
from plumed._core import (
    FormatError,
    InputBuilder,
    LeptonError,
    Plumed,
    PlumedError,
    hills_time_average,
    read_as_pandas,
    write_pandas,
)

__all__ = [
    # Core classes
    "Plumed",
    "InputBuilder",
    # Exceptions
    "PlumedError",
    "LeptonError",
    "FormatError",
    # Functions
    "read_as_pandas",
    "write_pandas",
    "hills_time_average",
    # Convenience functions
    "get_kernel_path",
    "get_plumed_path",
    "get_include_path",
]


def _get_package_dir() -> Path:
    """Get the directory where this package is installed."""
    return Path(__file__).parent


def get_kernel_path() -> str | None:
    """
    Get the path to the bundled PLUMED kernel library.

    Returns the absolute path to the bundled libplumedKernel.so (Linux) or
    libplumedKernel.dylib (macOS) if it exists, otherwise returns None.

    Returns:
        str or None: Path to the kernel library, or None if not bundled.

    Example:
        >>> import plumed
        >>> kernel = plumed.get_kernel_path()
        >>> if kernel:
        ...     p = plumed.Plumed(kernel=kernel)
        ... else:
        ...     p = plumed.Plumed()  # Uses PLUMED_KERNEL env var
    """
    lib_dir = _get_package_dir() / "_lib"

    if platform.system() == "Darwin":
        kernel_name = "libplumedKernel.dylib"
    else:
        kernel_name = "libplumedKernel.so"

    kernel_path = lib_dir / kernel_name
    if kernel_path.exists():
        return str(kernel_path.resolve())

    return None


def get_plumed_path() -> str | None:
    """
    Get the path to the bundled plumed executable.

    Returns the absolute path to the bundled plumed command-line tool
    if it exists, otherwise returns None.

    Returns:
        str or None: Path to the plumed executable, or None if not bundled.

    Example:
        >>> import plumed
        >>> import subprocess
        >>> plumed_exe = plumed.get_plumed_path()
        >>> if plumed_exe:
        ...     result = subprocess.run([plumed_exe, "info", "--version"],
        ...                             capture_output=True, text=True)
        ...     print(result.stdout)
    """
    bin_dir = _get_package_dir() / "_bin"
    plumed_path = bin_dir / "plumed"

    if plumed_path.exists():
        return str(plumed_path.resolve())

    return None


def get_include_path() -> str | None:
    """
    Get the path to PLUMED header files for compilation.

    Returns the path to the directory containing Plumed.h if bundled,
    otherwise returns None.

    Returns:
        str or None: Path to include directory, or None if not available.

    Example:
        >>> import plumed
        >>> include = plumed.get_include_path()
        >>> # Use in compilation: gcc -I{include} ...
    """
    include_dir = _get_package_dir() / "_include"
    if include_dir.exists():
        return str(include_dir.resolve())
    return None


def _setup_kernel_environment() -> None:
    """
    Set up PLUMED_KERNEL environment variable if bundled kernel is available.

    This function is called automatically on import to configure the
    environment for using the bundled PLUMED kernel, if the user hasn't
    already set PLUMED_KERNEL.
    """
    if "PLUMED_KERNEL" not in os.environ:
        kernel_path = get_kernel_path()
        if kernel_path:
            os.environ["PLUMED_KERNEL"] = kernel_path


# Automatically set up kernel environment on import
_setup_kernel_environment()
