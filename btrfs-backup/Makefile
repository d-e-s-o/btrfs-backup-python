# Makefile

#/***************************************************************************
# *   Copyright (C) 2014-2016 Daniel Mueller (deso@posteo.net)              *
# *                                                                         *
# *   This program is free software: you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation, either version 3 of the License, or     *
# *   (at your option) any later version.                                   *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU General Public License for more details.                          *
# *                                                                         *
# *   You should have received a copy of the GNU General Public License     *
# *   along with this program.  If not, see <http://www.gnu.org/licenses/>. *
# ***************************************************************************/

ROOT := $(shell pwd)/..
PYTHONPATH := "$(ROOT)/cleanup/src:$(ROOT)/execute/src:$(ROOT)/btrfs-backup/src:${PYTHONPATH}"


.PHONY: test
test:
	@PYTHONPATH="$(PYTHONPATH)"\
	 PYTHONDONTWRITEBYTECODE=1\
		python -m unittest --verbose --buffer deso.btrfs.test.allTests


.PHONY: %
%:
	@echo "Running deso.btrfs.test.$@ ..."
	@PYTHONPATH="$(PYTHONPATH)"\
	 PYTHONDONTWRITEBYTECODE=1\
		python -m unittest --verbose --buffer deso.btrfs.test.$@


ifneq (,$(filter testSetup testAll,$(MAKECMDGOALS)))
.PHONY: testSetup
# TODO: At the moment we do not delete the directory because it is full
#       of stuff and a 'rm -r' is not desired here. Find a satisfactory
#       solution to this issue.
testSetup: DIR := $(shell mktemp --directory --quiet)
testSetup:
	@git clone --quiet $(ROOT) $(DIR)
	@(export PYTHONPATH="$(PYTHONPATH)";\
	  cd $(DIR)/btrfs-backup &&\
	    python setup.py --version > /dev/null &&\
	    python setup.py --description > /dev/null &&\
	    python setup.py test &&\
	    python setup.py build &&\
	    python setup.py clean &&\
	    python setup.py sdist &&\
	    python setup.py bdist &&\
	    python setup.py clean)


.PHONY: testAll
testAll: test testSetup
endif
