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
	-rm -rf .nox .pytest_cache
	-find . -name "*.pyc" -delete
	-find . -name "*.pyo" -delete
	-find . -name "htmlcov" -type d -exec rm -r "{}" \;
	-find . -name "__pycache__" -exec rm -r "{}" \;
	-rm -r build
	-rm -r src/persist.egg-info
	-rm -r doc/README_files/
	-rm *.html

.PHONY: test clean auto
