import logging
from spine.identity import PermissionsValidator, PermissionDenied

# Configure logging to see output if needed
logging.basicConfig(level=logging.INFO)

def test_evaluate_request_empty_capabilities():
    """
    Test that an empty list of required capabilities returns True for any valid role.
    """
    print("Running test_evaluate_request_empty_capabilities...")
    perms = PermissionsValidator()

    # Existing roles
    assert perms.evaluate_request("scraper_agent", []) is True
    assert perms.evaluate_request("coder_agent", []) is True
    assert perms.evaluate_request("user", []) is True

    print("test_evaluate_request_empty_capabilities: PASSED")

def test_evaluate_request_standard_cases():
    """
    Test standard success and failure cases to ensure baseline functionality.
    """
    print("Running test_evaluate_request_standard_cases...")
    perms = PermissionsValidator()

    # Success case
    assert perms.evaluate_request("scraper_agent", ["network_read"]) is True

    # Failure case: unauthorized capability
    try:
        perms.evaluate_request("scraper_agent", ["bash"])
        assert False, "Should have raised PermissionDenied for 'bash' capability"
    except PermissionDenied:
        pass

    # Success case: wildcard
    assert perms.evaluate_request("user", ["any_capability", "another_one"]) is True

    print("test_evaluate_request_standard_cases: PASSED")

def test_evaluate_request_invalid_role():
    """
    Test that an unknown role raises PermissionDenied.
    """
    print("Running test_evaluate_request_invalid_role...")
    perms = PermissionsValidator()

    try:
        perms.evaluate_request("non_existent_role", [])
        assert False, "Should have raised PermissionDenied for unknown role"
    except PermissionDenied:
        pass

    print("test_evaluate_request_invalid_role: PASSED")

if __name__ == "__main__":
    try:
        test_evaluate_request_empty_capabilities()
        test_evaluate_request_standard_cases()
        test_evaluate_request_invalid_role()
        print("\nAll Identity Edge Case tests PASSED successfully!")
    except AssertionError as e:
        print(f"\nTest FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        exit(1)
