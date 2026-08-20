package billing

type BillingService struct {
	currency string
}

func NewBillingService(currency string) *BillingService {
	return &BillingService{currency: currency}
}

func (b *BillingService) Charge(amount float64) bool {
	return amount > 0
}
