from app.services.grading_service import GradingService

def test_fraction_decimal_equivalence(): assert GradingService().equivalent('0.5','1/2')
def test_text_normalization(): assert GradingService().equivalent(' X = 6 ','x=6')
def test_different_answers(): assert not GradingService().equivalent('7','6')
