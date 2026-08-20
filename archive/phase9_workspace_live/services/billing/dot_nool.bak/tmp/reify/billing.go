package billing

type BillingService struct {
	currency string
}

func NewBillingService(curr string) *BillingService {
	return &BillingService{currency: curr}
}

func (b *BillingService) Charge(amt float64) bool {
	return amt > 0
}
