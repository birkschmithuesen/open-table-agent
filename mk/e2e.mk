E2E_TARGETS += e2e-sync e2e-run e2e-shim e2e-boot
.PHONY: e2e-run e2e-sync e2e-shim e2e-boot
e2e-boot:
	python3 -m unittest -v e2e.tests.test_boot
e2e-shim:
	python3 -m unittest -v e2e.tests.test_build_shim e2e.tests.test_apt_proxy
e2e-run: e2e/node_modules/.ota-stamp
	python3 e2e/stack.py up || { python3 e2e/stack.py down; exit 1; }
	python3 e2e/bootstrap.py > e2e/.env.e2e ; status=$$?; \
	if [ $$status -eq 0 ]; then npm run build --prefix server && (cd e2e && npx vitest run); status=$$?; fi; \
	python3 e2e/stack.py down; exit $$status
e2e-sync:
	python3 -m unittest -v e2e.tests.test_sync_real
e2e/node_modules/.ota-stamp: e2e/package-lock.json
	cd e2e && npm ci --no-audit --no-fund
	touch $@
