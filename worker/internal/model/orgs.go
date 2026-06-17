package model

// OrgWithRole is an organizations row joined with the caller's membership role
// (the shape returned by GET /orgs). The base Organization row struct + the
// OrgMembership row struct live in model.go; this carries just the projected
// columns the orgs endpoints select.
type OrgWithRole struct {
	ID   string
	Name string
	Slug string
	Role string
}

// OrgMember is an org_memberships row joined with the member's profile (the
// shape returned by GET /orgs/{orgID}/members). Email/full_name/avatar_url are
// pointer types because the profile columns are nullable on the wire (mirror
// OrgMemberResponse in orgs.py); avatar_url is genuinely nullable in profiles.
type OrgMember struct {
	UserID    string
	Role      string
	Email     *string
	FullName  *string
	AvatarURL *string
}
