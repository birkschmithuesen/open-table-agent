# open-table-agent — top-level Makefile.
#
# Each build chain owns exactly one fragment in mk/ (see docs/superpowers/specs/*-design.md §7.1):
#   mk/server.mk (Chain A), mk/patches.mk (Chain B), mk/sync.mk (Chain C), mk/e2e.mk (Chain D).
# A fragment registers its target by appending to TEST_TARGETS (or E2E_TARGETS) and must not edit
# this file. `make test` / `make e2e` fail loudly when nothing is registered: no silent green.
#
# Targeted runs: `make test server/test/http.test.ts patches/tests` — extra goals are collected in
# TEST_ARGS; a fragment registers itself only if an arg lies under its directory (or no args given).

TEST_TARGETS :=
E2E_TARGETS :=

# Extra command-line goals = test path arguments.
TEST_ARGS := $(filter-out test e2e,$(MAKECMDGOALS))

# $(call ota_args,DIR): the TEST_ARGS that lie under DIR/ (or equal DIR).
ota_args = $(filter $(1) $(1)/%,$(TEST_ARGS))
# $(call ota_selected,DIR): non-empty if the fragment owning DIR should run.
ota_selected = $(if $(TEST_ARGS),$(call ota_args,$(1)),all)

# Directories a fragment may own; a path argument outside all of them is an error, not a skip.
OTA_ROOTS := server patches scripts e2e
OTA_UNOWNED_ARGS := $(filter-out $(foreach r,$(OTA_ROOTS),$(r) $(r)/%),$(TEST_ARGS))
ifneq ($(OTA_UNOWNED_ARGS),)
$(error make: path argument(s) outside $(OTA_ROOTS): $(OTA_UNOWNED_ARGS))
endif

-include $(sort $(wildcard mk/*.mk))

.DEFAULT_GOAL := test
.PHONY: test e2e

test: $(TEST_TARGETS)
	@if [ -z "$(strip $(TEST_TARGETS))" ]; then \
	  echo "make test: FAIL - no test target selected (mk/*.mk registered none$(if $(TEST_ARGS), for: $(TEST_ARGS)))" >&2; \
	  exit 2; \
	fi
	@echo "make test: OK ($(strip $(TEST_TARGETS)))"

e2e: $(E2E_TARGETS)
	@if [ -z "$(strip $(E2E_TARGETS))" ]; then \
	  echo "make e2e: FAIL - no e2e target registered (mk/e2e.mk missing)" >&2; \
	  exit 2; \
	fi
	@echo "make e2e: OK ($(strip $(E2E_TARGETS)))"

# Path arguments are goals too; make them silent no-ops.
ifneq ($(TEST_ARGS),)
.PHONY: $(TEST_ARGS)
$(TEST_ARGS):
	@:
endif
