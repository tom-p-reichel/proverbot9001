SHELL=/usr/bin/env bash

NTHREADS=16
FLAGS=

SITE_SERVER=goto
SITE_DIR=~alexss/proverbot9001-site/workshop/
SITE_PATH=$(SITE_SERVER):$(SITE_DIR)

ifeq ($(NUM_FILES),)
HEAD_CMD=cat
else
HEAD_CMD=head -n $(NUM_FILES)
endif

ifneq ($(MESSAGE),)
FLAGS+=-m "$(MESSAGE)"
endif
REPORT="report"

.PHONY: scrape report setup

all: scrape report

setup:
	./src/setup.sh && $(MAKE) publish-depv

scrape:
	mv data/scrape.txt data/scrape.bkp 2>/dev/null || true
	cat data/sf-files.txt | $(HEAD_CMD) | \
	xargs python3 src/scrape2.py $(FLAGS) -j $(NTHREADS) --output data/scrape.txt \
				        		     --prelude software-foundations
report:
	cat data/sf-test-files.txt | $(HEAD_CMD) | \
	xargs ./src/proverbot9001.py static-report -j $(NTHREADS) --predictor=regex --weightsfile=data/regex-weights.tar --prelude ./software-foundations $(FLAGS)

train:
	./src/proverbot9001.py train regex data/scrape.txt data/regex-weights.tar $(FLAGS)

INDEX_FILES=index.js index.css build-index.py

reports/index.css: reports/index.scss
	sass $^ $@

update-index: $(addprefix reports/, $(INDEX_FILES))
	rsync -avz $(addprefix reports/, $(INDEX_FILES)) $(SITE_PATH)/reports/
	ssh goto 'cd $(SITE_DIR)/reports && \
		  python3 build-index.py'

publish:
	$(eval REPORT_NAME := $(shell ./reports/get-report-name.py $(REPORT)/))
	mv $(REPORT) $(REPORT_NAME)
	chmod +rx $(REPORT_NAME)
	tar czf report.tar.gz $(REPORT_NAME)
	rsync -avz report.tar.gz $(SITE_PATH)/reports/
	ssh goto 'cd ~alexss/proverbot9001-site/reports && \
                  tar xzf report.tar.gz && \
                  rm report.tar.gz && \
		  chgrp -Rf proverbot9001 $(REPORT_NAME) $(INDEX_FILES) && \
		  chmod -Rf g+rw $(REPORT_NAME) $(INDEX_FILES) || true'
	mv $(REPORT_NAME) $(REPORT)
	$(MAKE) update-index


publish-depv:
	opam info -f name,version menhir ocamlfind ppx_deriving ppx_import cmdliner core_kernel sexplib ppx_sexp_conv camlp5 | awk '{print; print ""}' > known-good-dependency-versions.md

clean:
	rm -rf report-*
	rm -f log*.txt
	fd '.*\.v\.lin' CompCert | xargs rm
