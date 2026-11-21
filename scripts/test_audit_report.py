import unittest

from audit_report import check


class RatioAuditTests(unittest.TestCase):
    def test_detects_fraction_percentage_mismatch(self):
        findings = check('男参与者 22/110（39.6%）。')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], 'percentage_mismatch')
        self.assertEqual(findings[0]['calculated_percent'], '20.00')
        self.assertEqual(findings[0]['line'], 1)

    def test_rounding_both_orders_and_full_width_percent(self):
        self.assertEqual(check('完成 1/3（33.3%）；结果为 50％ (1/2)。'), [])

    def test_zero_denominator_is_reported(self):
        findings = check('有效人数 2/0（0%）。')
        self.assertEqual(findings[0]['kind'], 'zero_denominator')

    def test_does_not_assume_unrelated_numbers_share_denominator(self):
        self.assertEqual(check('A组22人，B组110人；B组39.6%有改善。'), [])


if __name__ == '__main__':
    unittest.main()
