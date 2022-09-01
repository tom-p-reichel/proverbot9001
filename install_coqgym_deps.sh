#!/usr/bin/env bash

if [[ -v $OPAMJOBS ]]
then
    OPAMJOBS=16
fi

if ! command -v ruby &> /dev/null
then
    # First, install Ruby, as that is for some reason required to build
    # the "system" project
    git clone https://github.com/rbenv/ruby-build.git ~/ruby-build
    mkdir -p ~/.local
    PREFIX=~/.local ~/ruby-build/install.sh
    ~/.local/ruby-build 3.1.2 ~/.local/
fi



git submodule update && git submodule init

# Sync opam state to local
rsync -av --delete $HOME/.opam.dir/ /tmp/${USER}_dot_opam | tqdm --desc="Reading shared opam state" > /dev/null

# Create the 8.10 switch
opam switch create coq-8.10 4.07.1
eval $(opam env --switch=coq-8.10 --set-switch)
opam pin -ny add coq 8.10.2
opam repo add coq-extra-dev https://coq.inria.fr/opam/extra-dev
opam repo add coq-released https://coq.inria.fr/opam/released
opam repo add psl-opam https://github.com/uds-psl/psl-opam-repository.git


# using pins to specify versions of packages we need, but DELAYING
# the install of those packages -- running no risk of having to recompile packages
# due to successive install commands

# coq-cheerios/coq-ext-lib master does not support coq-8.10
opam pin -ny add coq-cheerios "git+https://github.com/uwplse/cheerios.git#f0c7659c44999c6cfcd484dc3182affc3ff4248a"
opam pin -ny add coq-ext-lib "git+https://github.com/coq-community/coq-ext-lib.git#506d2985cc540ad7b4a788d9a20f6ec57e75a510"
opam pin -ny add coq-lin-alg https://github.com/tom-p-reichel/lin-alg-8.10.git
opam pin -ny add coq-metalib "git+https://github.com/plclub/metalib.git#021bea02c86d80849d9e353eefec3cd165ba3be4"
opam pin -ny add coq-bellantonicook "git+https://github.com/tom-p-reichel/bellantonicook.git"
#opam pin -ny add coq-psl-base-library "git+https://github.com/uds-psl/base-library"
opam pin -ny add menhir 20190626


# Install dependency packages for 8.10
opam install -y coq-serapi \
     coq-struct-tact \
     coq-inf-seq-ext \
     coq-verdi \
     coq-smpl \
     coq-int-map \
     coq-pocklington \
     coq-mathcomp-ssreflect coq-mathcomp-bigenough coq-mathcomp-algebra\
     coq-fcsl-pcm \
     coq-simple-io \
     coq-list-string \
     coq-error-handlers \
     coq-function-ninjas \
     coq-algebra \
     coq-zorns-lemma \
     coq-metalib.dev \
     coq-cheerios \
     coq-ext-lib \
     coq-lin-alg \
     coq-psl-base-library \
     coq-bellantonicook \
     menhir

# coq-equations seems to rely on ocamlfind for it's build, but doesn't
# list it as a dependency, so opam sometimes tries to install
# coq-equations before ocamlfind. Splitting this into a separate
# install call prevents that.
opam install -y coq-equations \
     coq-metacoq coq-metacoq-checker coq-metacoq-template

# Create the coq 8.12 switch
mkdir deps
# TODO: fix all versions that are downloaded from git like above
opam switch create coq-8.12 4.07.1
eval $(opam env --switch=coq-8.12 --set-switch)
opam pin add -y coq 8.12.2

# Install the packages that can be installed directly through opam
opam repo add coq-released https://coq.inria.fr/opam/released
opam repo add coq-extra-dev https://coq.inria.fr/opam/extra-dev
opam install -y coq-serapi \
     coq-smpl=8.12 coq-metacoq-template coq-metacoq-checker \
     coq-equations \
     coq-mathcomp-ssreflect coq-mathcomp-algebra coq-mathcomp-field \
     menhir

# Install some coqgym deps that don't have the right versions in their
# official opam packages
git clone git@github.com:uwplse/StructTact.git deps/StructTact
(cd deps/StructTact && opam install -y . )
git clone git@github.com:DistributedComponents/InfSeqExt.git deps/InfSeqExt
(cd deps/InfSeqExt && opam install -y . )

# Cheerios has its own issues
opam pin -ny coq-cheerios "git+https://github.com/uwplse/cheerios.git#9c7f66e57b91f706d70afa8ed99d64ed98ab367d"
opam install -y --ignore-constraints-on=coq coq-cheerios

(cd coq-projects/verdi && opam install -y --ignore-constraints-on=coq . )
(cd coq-projects/fcsl-pcm && make "$@" && make install)

# Finally, sync the opam state back to global
rsync -av --delete /tmp/${USER}_dot_opam/ $HOME/.opam.dir | tqdm --desc="Writing shared opam state" > /dev/null

