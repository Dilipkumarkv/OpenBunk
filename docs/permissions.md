# DeepBNK — Permission Matrix (Phase 05)

Server-side enforced. UI hiding is never authorization. `/audit` lists `owner` + `auditor` only.
Any access outside this matrix returns 403 (or 404 for foreign-station resources, by design).

| Capability                                    | owner | manager | cashier | accountant | auditor |
| --------------------------------------------- | :---: | :-----: | :-----: | :--------: | :-----: |
| `GET /station`                                |   ✓   |    ✓    |    ✓    |     ✓      |    ✓    |
| `PUT /station` (+ re-auth)                    |   ✓   |         |         |            |         |
| `GET /employees` staff list                   |   ✓   |         |         |            |         |
| `POST /employees` create staff                |   ✓   |         |         |            |         |
| `PUT /employees/{id}/role` (+ re-auth)        |   ✓   |         |         |            |         |
| `DELETE /employees/{id}` offboard (+ re-auth) |   ✓   |         |         |            |         |
| `GET /fuel-products` `/tanks` `/nozzles`      |   ✓   |    ✓    |    ✓    |     ✓      |    ✓    |
| `POST /fuel-products` `/tanks` `/nozzles`     |   ✓   |    ✓    |         |            |         |
| `POST /tanks/{id}/adjustments` (+ re-auth)    |   ✓   |    ✓    |         |            |         |
| `GET /tanks/{id}/stock`                       |   ✓   |    ✓    |    ✓    |     ✓      |    ✓    |
| `GET /shifts` list/detail/readings            |   ✓   |    ✓    |    ✓    |     ✓      |    ✓    |
| `POST /shifts` open                           |   ✓   |    ✓    |    ✓    |            |         |
| `PUT /shifts/{id}/readings`                   |   ✓   |    ✓    |    ✓    |            |         |
| `POST /shifts/{id}/validate`                  |   ✓   |    ✓    |    ✓    |     ✓      |    ✓    |
| `POST /shifts/{id}/close` (+ re-auth)         |   ✓   |    ✓    |         |            |         |
| `GET /fuel-receipts`                          |   ✓   |    ✓    |    ✓    |     ✓      |    ✓    |
| `POST /fuel-receipts`                         |   ✓   |    ✓    |         |            |         |
| `POST /sales`                                 |   ✓   |    ✓    |    ✓    |            |         |
| `GET /sales`                                  |   ✓   |    ✓    |         |     ✓      |    ✓    |
| `GET /credit/customers` ledger                |   ✓   |    ✓    |         |     ✓      |         |
| `POST /credit/customers` entries              |   ✓   |    ✓    |         |     ✓      |         |
| `GET /reports/*`                              |   ✓   |    ✓    |         |     ✓      |    ✓    |
| `GET /audit`                                  |   ✓   |         |         |            |    ✓    |
| `GET /export` (+ re-auth)                     |   ✓   |         |         |            |         |
| `DELETE /session`, `POST /session/refresh`    |   ✓   |    ✓    |    ✓    |     ✓      |    ✓    |

Notes:

- Station scoping is mandatory on every query (cross-station access returns 404/empty).
- `+ re-auth` endpoints additionally require the caller's PIN in the `X-Reauth-Pin` header.
- Auditor is read-only: reports and audit trail exclusively.
- Accountant is financial: reports, credit ledger, sales list; no dispenser/meter edits.
