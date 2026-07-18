from app.security.password_hashing import PasswordService


def test_hash_produces_an_argon2id_tagged_value():
    service = PasswordService()
    hashed = service.hash("correct-horse-battery-staple")
    assert hashed.startswith("$argon2id$")


def test_hash_is_salted_and_differs_across_calls():
    service = PasswordService()
    first = service.hash("same-password")
    second = service.hash("same-password")
    assert first != second


def test_verify_succeeds_for_the_correct_password():
    service = PasswordService()
    hashed = service.hash("my-real-password")
    assert service.verify("my-real-password", hashed) is True


def test_verify_fails_for_the_wrong_password():
    service = PasswordService()
    hashed = service.hash("my-real-password")
    assert service.verify("not-my-password", hashed) is False


def test_verify_fails_gracefully_for_a_malformed_hash():
    service = PasswordService()
    assert service.verify("anything", "not-a-real-argon2-hash") is False


def test_verify_dummy_does_not_raise():
    service = PasswordService()
    service.verify_dummy()  # must never raise, regardless of outcome
