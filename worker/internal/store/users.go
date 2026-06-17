package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"regexp"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// execer is satisfied by both *sql.DB and *sql.Tx so repository helpers work
// inside or outside a transaction.
type execer interface {
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
}

const profileCols = "id, email, full_name, avatar_url, is_active, password_hash, created_at, updated_at"

func scanProfile(row interface{ Scan(...any) error }) (*model.Profile, error) {
	var p model.Profile
	if err := row.Scan(&p.ID, &p.Email, &p.FullName, &p.AvatarURL, &p.IsActive,
		&p.PasswordHash, &p.CreatedAt, &p.UpdatedAt); err != nil {
		return nil, err
	}
	return &p, nil
}

// GetProfileByEmail does a case-insensitive lookup; returns (nil, nil) if absent.
func GetProfileByEmail(ctx context.Context, q execer, email string) (*model.Profile, error) {
	row := q.QueryRowContext(ctx,
		"SELECT "+profileCols+" FROM profiles WHERE lower(email) = lower(?)", email)
	p, err := scanProfile(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return p, err
}

// GetProfileByID returns (nil, nil) if absent.
func GetProfileByID(ctx context.Context, q execer, id string) (*model.Profile, error) {
	row := q.QueryRowContext(ctx, "SELECT "+profileCols+" FROM profiles WHERE id = ?", id)
	p, err := scanProfile(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return p, err
}

func SetPasswordHash(ctx context.Context, q execer, id, hash string) error {
	_, err := q.ExecContext(ctx,
		"UPDATE profiles SET password_hash = ?, updated_at = ? WHERE id = ?",
		hash, util.NowISO(), id)
	return err
}

var slugRe = regexp.MustCompile(`[^a-z0-9]+`)

func slugify(value string) string {
	s := strings.Trim(slugRe.ReplaceAllString(strings.ToLower(value), "-"), "-")
	if s == "" {
		return "org"
	}
	return s
}

func uniqueSlug(ctx context.Context, q execer, base string) (string, error) {
	slug := slugify(base)
	candidate := slug
	for n := 1; ; n++ {
		var existing string
		err := q.QueryRowContext(ctx,
			"SELECT id FROM organizations WHERE slug = ?", candidate).Scan(&existing)
		if errors.Is(err, sql.ErrNoRows) {
			return candidate, nil
		}
		if err != nil {
			return "", err
		}
		candidate = fmt.Sprintf("%s-%d", slug, n+1)
	}
}

// GetOrCreateUser returns the existing profile for email, or creates a profile +
// personal organization + owner membership (ports app/auth/provisioning.py
// get_or_create_user). Run inside a transaction by the caller.
func GetOrCreateUser(ctx context.Context, tx execer, email string, fullName, avatarURL *string) (*model.Profile, error) {
	if existing, err := GetProfileByEmail(ctx, tx, email); err != nil {
		return nil, err
	} else if existing != nil {
		return existing, nil
	}

	name := ""
	if fullName != nil && *fullName != "" {
		name = *fullName
	} else {
		name = strings.SplitN(email, "@", 2)[0]
	}

	now := util.NowISO()
	profileID := util.NewUUID()
	if _, err := tx.ExecContext(ctx,
		"INSERT INTO profiles(id, email, full_name, avatar_url, is_active, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
		profileID, email, name, avatarURL, true, now, now); err != nil {
		return nil, err
	}

	slug, err := uniqueSlug(ctx, tx, strings.SplitN(email, "@", 2)[0])
	if err != nil {
		return nil, err
	}
	orgID := util.NewUUID()
	if _, err := tx.ExecContext(ctx,
		"INSERT INTO organizations(id, name, slug, settings, created_at, updated_at) VALUES (?,?,?,?,?,?)",
		orgID, name+"'s Organization", slug, "{}", now, now); err != nil {
		return nil, err
	}
	if _, err := tx.ExecContext(ctx,
		"INSERT INTO org_memberships(id, org_id, user_id, role, joined_at) VALUES (?,?,?,?,?)",
		util.NewUUID(), orgID, profileID, "owner", now); err != nil {
		return nil, err
	}

	return GetProfileByID(ctx, tx, profileID)
}
