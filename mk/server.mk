ifneq ($(call ota_selected,server),)
TEST_TARGETS += test-server
endif
.PHONY: test-server
test-server: server/node_modules/.ota-stamp
	cd server && npx tsc --noEmit && npx vitest run $(patsubst server/%,%,$(filter-out server,$(call ota_args,server)))

server/node_modules/.ota-stamp: server/package-lock.json
	cd server && npm ci --no-audit --no-fund
	touch $@
