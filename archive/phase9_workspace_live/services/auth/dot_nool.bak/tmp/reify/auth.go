package auth

type AuthService struct {
	secret string
}

func NewAuthService(s string) *AuthService {
	return &AuthService{secret: s}
}

func (a *AuthService) Verify(token string) bool {
	return token == a.secret
}
