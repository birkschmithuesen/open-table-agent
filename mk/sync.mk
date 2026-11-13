ifneq ($(call ota_selected,scripts),)
TEST_TARGETS += test-sync
endif
.PHONY: test-sync
test-sync:
	python3 -m unittest discover -s scripts/tests -t . -v
