// Package model holds the row structs for the worker-owned SQLite tables. Fields
// mirror the columns in app/db/models.py. Structs are added per phase as the
// endpoints that use them are ported.
package model

type Profile struct {
	ID           string
	Email        string
	FullName     string
	AvatarURL    *string
	IsActive     bool
	PasswordHash *string
	CreatedAt    string
	UpdatedAt    string
}

type Organization struct {
	ID        string
	Name      string
	Slug      string
	Domain    *string
	Settings  string // JSON
	CreatedAt string
	UpdatedAt string
}

type OrgMembership struct {
	ID       string
	OrgID    string
	UserID   string
	Role     string
	JoinedAt string
}
