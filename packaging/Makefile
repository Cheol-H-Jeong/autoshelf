PYTHON ?= python

build-linux:
	$(PYTHON) packaging/build.py --verify-install --verify-wheel

manpage:
	$(PYTHON) packaging/generate_manpage.py

bump-patch:
	$(PYTHON) packaging/bump_version.py patch

bump-minor:
	$(PYTHON) packaging/bump_version.py minor

bump-major:
	$(PYTHON) packaging/bump_version.py major

release:
	@test -n "$(VERSION)"
	$(PYTHON) packaging/generate_manpage.py
	$(PYTHON) packaging/build.py --verify-install --verify-wheel
