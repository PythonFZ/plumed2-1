# Minimal Makefile to satisfy PLUMED build system
# The actual Python build is handled by hatchling/pyproject.toml

.PHONY: all clean install

all:
	@echo "Python interface is built via pyproject.toml"

clean:
	@echo "Cleaning Python build artifacts"
	rm -rf build dist *.egg-info
	rm -rf plumed/_lib plumed/_bin plumed/_include
	rm -f plumed/*.so plumed/*.dylib plumed/*.pyd plumed/_core.c

install:
	@echo "Python interface is installed via pip/uv"
