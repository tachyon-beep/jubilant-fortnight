# Production Issues Found During Test Cleanup

## Critical Issue 1: Memory.get_feeling() Method Missing
- **Location**: `great_work/service.py` line 701 and 702
- **Test**: `tests/test_contracts.py::TestOfferEvaluation::test_evaluate_basic_offer` and related tests
- **Expected**: Memory class should have a `get_feeling()` method
- **Actual**: Memory class only has a `feelings` dict that should be accessed directly
- **Evidence**:
  ```python
  # In service.py line 701:
  rival_feeling = scholar.memory.get_feeling(offer.rival_id)  # AttributeError
  # Should be:
  rival_feeling = scholar.memory.feelings.get(offer.rival_id, 0.0)
  ```
- **Impact**: The `evaluate_scholar_offer()` method in GameService will crash when called
- **Investigation**: Check all uses of `scholar.memory.get_feeling()` in production code and replace with `scholar.memory.feelings.get(key, 0.0)`

## Critical Issue 2: Scholar Offer Resolution System
- **Tests**: All offer evaluation and resolution tests in `test_contracts.py`
- **Description**: The entire defection offer evaluation and resolution system appears to be broken due to the Memory API issue
- **Affected Methods**:
  - `GameService.evaluate_scholar_offer()`
  - `GameService.resolve_offer_negotiation()` (likely)
  - Any other methods that evaluate scholar feelings
- **Impact**: Contract negotiation and scholar defection features are completely non-functional

## Moderate Issue 3: Expedition Record Persistence Schema Mismatch
- **Test**: `tests/test_state_edge_cases.py::test_expedition_record_can_be_stored`
- **Expected**: Test expects different column structure than production provides
- **Actual**: Production schema is correct but test assumptions were wrong
- **Evidence**: Tests were using wrong column indices for expeditions table
- **Impact**: None - production code is correct, tests were wrong
- **Investigation**: Already fixed in tests

## Moderate Issue 4: GameState Methods for Handling Malformed Data
- **Test**: `tests/test_state_edge_cases.py::test_all_players_with_malformed_data`
- **Expected**: GameState should handle malformed JSON data gracefully
- **Actual**: Test still failing - needs investigation
- **Impact**: Could cause crashes when loading corrupted database data
- **Investigation**: Check GameState's JSON parsing and error handling

## Documentation Issues

### Issue 5: API Inconsistency - advance_timeline Return Values
- **Location**: `great_work/state.py` method `advance_timeline()`
- **Description**: When no time advancement occurs, returns `(0, current_year)` instead of `(current_year, current_year)`
- **Impact**: Confusing API that could lead to bugs in calling code
- **Recommendation**: Document this behavior clearly or change to return `(current_year, current_year)` for consistency

## Test Suite Status After Fixes

### Before Fixes:
- **Total Tests**: 157
- **Passing**: 117
- **Failing**: 40
- **Pass Rate**: 74.5%

### After Test Fixes (Estimated):
- **Total Tests**: 157
- **Passing**: ~147
- **Still Failing**: ~10 (due to production bugs)
- **Pass Rate**: ~93.6%

### Files with Remaining Production Issues:
1. **test_contracts.py**: 7-9 tests failing due to Memory.get_feeling() production bug
2. **test_state_edge_cases.py**: 1-2 tests may still fail due to data handling issues
3. **test_service_theories.py**: Possibly 1-2 tests with service method issues
4. **test_sideways_effects.py**: Unknown number of integration test failures

## Recommended Actions

1. **URGENT**: Fix the `Memory.get_feeling()` issue in `service.py`:
   - Replace all `scholar.memory.get_feeling(key)` with `scholar.memory.feelings.get(key, 0.0)`
   - This will fix the entire contract negotiation system

2. **HIGH**: Review and fix the offer evaluation system:
   - Ensure all scholar feeling evaluations use the correct Memory API
   - Add integration tests for the complete offer flow

3. **MEDIUM**: Improve error handling for malformed data:
   - Add try/catch blocks around JSON parsing
   - Provide sensible defaults or error messages

4. **LOW**: Document the advance_timeline API behavior or make it more intuitive

## Summary

The most critical issue is the Memory API mismatch in production code. The `GameService.evaluate_scholar_offer()` method and related contract negotiation features are completely broken due to calling a non-existent `get_feeling()` method. This is a simple fix but has major impact on gameplay features.

Most other test failures were due to tests using outdated or incorrect APIs, which have been fixed. The production code is generally solid except for the Memory API issue.