# All commands are provided through python setup.py so that they are
# platform independent.  These are included here simply as a
# convenience.

test:
	nox

README.rst: doc/README.ipynb
	jupyter nbconvert --to=rst --output=README.rst doc/README.ipynb

%.html: %.rst
	rst2html5.py $< > $@

%.html: %.md
	pandoc $< -o $@ --standalone && open -g -a Safari $@
	fswatch -e ".*\.html" -o . | while read num ; do pandoc $< -o $@ --standalone && open -g -a Safari $@; done


clean:
	-$(RM) -r .pytest_cache build src/persist.egg-info
	-$(RM) -r doc/README_files/
	-$(RM) *.html *.xml .coverage
	-find . -type f -name "*.py[oc]" -delete
	-find . -type d \( -name "htmlcov" -o \
	                   -name "__pycache__" -o \
	                   -name "_build" -o \
	                   -name ".ipynb_checkpoints" \) \
        -exec $(RM) -r "{}" +

realclean: clean
	-$(RM) -r .nox

.PHONY: test clean realclean auto
