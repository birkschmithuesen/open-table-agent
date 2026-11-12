ifneq ($(call ota_selected,patches),)
TEST_TARGETS += test-patches
endif
.PHONY: test-patches
test-patches:
	python3 -m unittest discover -s patches/tests -t . -v
