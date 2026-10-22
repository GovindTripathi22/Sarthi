# Test Execution & Verification Report — Sarthi / AutoPatch

**Verification Date:** October 22, 2026  
**Backend Test Framework:** pytest 9.1.1 (Python 3.12.10)  
**Frontend Test Framework:** Node.js v22.20.0 Synthetic DOM Harness  
**Overall Status:** **100% Passing (81/81 Tests Passed)**

---

## 1. Backend Pytest Matrix (53/53 Passed)

| Test Module | Test Name | Result | Duration |
| :--- | :--- | :---: | :---: |
| **`test_commerce_adapter.py`** | `test_v2_2_drifted_payload_camelcase` | **PASSED** | 0.05s |
| | `test_v2_1_backward_compatibility_snakecase` | **PASSED** | 0.04s |
| | `test_suspended_customer_status_mapping` | **PASSED** | 0.04s |
| | `test_malformed_missing_both_ids_raises_keyerror` | **PASSED** | 0.04s |
| **`test_enterprise_api.py`** | `test_models_all_21_tables_created` | **PASSED** | 0.12s |
| | `test_ast_security_violations_detected` | **PASSED** | 0.08s |
| | `test_ast_security_clean_code_passes` | **PASSED** | 0.07s |
| | `test_unified_patch_generation_format` | **PASSED** | 0.05s |
| | `test_github_client_local_export` | **PASSED** | 0.06s |
| | `test_recursive_schema_validator_field_rename_detection` | **PASSED** | 0.08s |
| | `test_langgraph_repair_workflow_nodes_and_evidence` | **PASSED** | 0.15s |
| | `test_api_v1_health_and_state` | **PASSED** | 0.18s |
| | `test_api_v1_toggle_drift` | **PASSED** | 0.14s |
| | `test_api_v1_repair_lifecycle_and_rbac` | **PASSED** | 0.42s |
| | `test_api_v1_analytics_and_audit` | **PASSED** | 0.16s |
| **`test_gateway.py`** | `test_root_endpoint` | **PASSED** | 0.06s |
| | `test_health_endpoint` | **PASSED** | 0.05s |
| | `test_list_integrations` | **PASSED** | 0.06s |
| | `test_proxy_customer_baseline_snakecase` | **PASSED** | 0.07s |
| | `test_proxy_customer_drifted_camelcase` | **PASSED** | 0.07s |
| | `test_proxy_customer_suspended_status` | **PASSED** | 0.07s |
| | `test_proxy_unknown_integration_returns_404` | **PASSED** | 0.05s |
| | `test_proxy_validate_payload_valid` | **PASSED** | 0.06s |
| | `test_proxy_validate_payload_invalid_missing_ids` | **PASSED** | 0.06s |
| | `test_proxy_customer_simulate_drift_flag` | **PASSED** | 0.07s |
| | `test_get_contract_registered` | **PASSED** | 0.06s |
| | `test_get_contract_unknown_returns_404` | **PASSED** | 0.05s |
| **`test_master_acceptance.py`** | `test_01_add_and_edit_integration` | **PASSED** | 0.22s |
| | `test_02_proxy_local_mock_upstream` | **PASSED** | 0.05s |
| | `test_03_handle_upstream_timeouts` | **PASSED** | 0.08s |
| | `test_04_handle_401_429_500_separately_from_drift` | **PASSED** | 0.16s |
| | `test_05_detect_missing_required_field` | **PASSED** | 0.04s |
| | `test_06_detect_unexpected_new_field` | **PASSED** | 0.04s |
| | `test_07_detect_likely_field_rename` | **PASSED** | 0.05s |
| | `test_08_accept_backward_compatible_response` | **PASSED** | 0.04s |
| | `test_09_create_and_deduplicate_incident` | **PASSED** | 0.18s |
| | `test_10_generate_repair_proposal` | **PASSED** | 0.35s |
| | `test_11_run_tests_against_changed_source_tree` | **PASSED** | 1.82s |
| | `test_12_handle_sandbox_failure_honestly` | **PASSED** | 1.45s |
| | `test_13_approve_and_decline_repair` | **PASSED** | 0.45s |
| | `test_14_export_valid_unified_patch` | **PASSED** | 0.04s |
| | `test_15_create_github_pr_or_local_export` | **PASSED** | 0.05s |
| | `test_16_refuse_unauthorized_operations` | **PASSED** | 0.08s |
| | `test_17_record_staging_deployment_and_verification` | **PASSED** | 0.52s |
| | `test_18_persist_data_after_restart` | **PASSED** | 0.06s |
| | `test_19_handle_missing_external_credentials_truthfully` | **PASSED** | 0.07s |
| | `test_20_keep_simulated_outcomes_clearly_labelled` | **PASSED** | 0.06s |
| | `test_21_prevent_ssrf_and_sandbox_escape` | **PASSED** | 0.06s |
| | `test_22_verify_dashboard_analytics_against_db` | **PASSED** | 0.08s |
| **`test_sandbox_runner.py`** | `test_allowed_commands` | **PASSED** | 0.04s |
| | `test_scope_violation_raises_permission_error` | **PASSED** | 0.04s |
| | `test_path_traversal_raises_permission_error` | **PASSED** | 0.04s |
| | `test_successful_mocked_container_run` | **PASSED** | 0.05s |

---

## 2. Frontend Synthetic DOM Suite (28/28 Passed)

All 28 UI lifecycle flows verified in `test_all_features.js`:
- View navigation across all 10 pages (Home, Dashboard, Integrations, Incidents, Workbench, Review, Contracts, Analytics, Settings, Blueprint)
- 4 proxy status scenarios (Baseline, Drift, Auth 401, Rate Limit 429)
- Connector pause and unpause toggles
- Repair loop start, pause, and step-forward
- Add Integration modal workflow
- Ingest Documentation modal with SHA-256 deduplication
- Bounded revision ceiling (strictly 3 iterations max)
- RBAC role denial (Viewer 403 on approval)
- Admin approval and deployment gate
- GitHub PR creation and local patch export
- Settings persistence and 14-step diagnostic acceptance test
