package service

// TaxBasisPoints is applied by Invoice on top of the order subtotal.
const TaxBasisPoints = 1000 // 10.00%

// Invoice returns the amount to charge for a subtotal, tax included,
// rounded down to whole cents.
func Invoice(subtotalCents int) int {
	return subtotalCents + subtotalCents*TaxBasisPoints/10000
}
