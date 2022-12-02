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
	-rm -r build
	-rm -r src/persist.egg-info
	-rm -r doc/README_files/
	-rm *.html
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "htmlcov" -exec rm -r "{}" +
	find . -type d -name "__pycache__" -exec rm -r "{}" +
	find . -type d -name "_build" -exec rm -rf "{}" +
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf "{}" +

.PHONY: test clean auto
