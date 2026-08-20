package auth

type AuthService struct {
	secret string
}

func NewAuthService(secret string) *AuthService {
	return &AuthService{secret: secret}
}

func (a *AuthService) Validate(token string) bool {
	return token == a.secret
}
