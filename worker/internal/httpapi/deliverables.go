package httpapi

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"encoding/xml"
	"net/http"
	"strings"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/llm"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/storage"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
	"github.com/go-chi/chi/v5"
)

// deliverablesBucket is the storage bucket deliverables are written to.
const deliverablesBucket = "deliverables"

// typeLabels mirrors TYPE_LABELS in app/api/v1/deliverables.py — the supported
// deliverable types and their display labels. An unsupported type is a 400.
var typeLabels = map[string]string{
	"investment_memo": "Investment Memo",
	"financial_model": "Financial Model",
	"ic_presentation": "IC Presentation",
}

// typePrompts mirrors _TYPE_PROMPTS in app/services/deliverable_service.py.
// investment_memo is the fallback for an unknown type (it can't be reached here
// because the handler rejects unknown types up front, but kept for parity).
var typePrompts = map[string]string{
	"investment_memo": "You are preparing an investment memo for a private-equity / investment-" +
		"banking team. Using the deal context below, produce a memo with these " +
		"Markdown sections in order: Executive Summary, Company Overview, " +
		"Financial Analysis, Market & Competition, Key Risks, Valuation, " +
		"Recommendation. Be specific and cite evidence from the transcripts / " +
		"documents where possible. Return Markdown only — no preamble.",
	"ic_presentation": "You are outlining an IC presentation deck. Using the deal context, " +
		"produce a Markdown document with one top-level section per slide: " +
		"Deal Overview, Investment Thesis (1), Investment Thesis (2), Market & " +
		"Competitive Landscape, Financial Summary, Projections, Key Risks & " +
		"Mitigants, Terms & Next Steps. Each section gets 3–6 bullet points. " +
		"Markdown only — no preamble.",
	"financial_model": "You are drafting the assumptions section of a financial model. Using " +
		"the deal context, produce a Markdown document titled 'Model " +
		"Assumptions' with sections: Revenue Drivers, Margin Assumptions, " +
		"Operating Costs, Capital Structure, Scenario Ranges (bear / base / " +
		"bull). Return Markdown only — no preamble.",
}

// docTitles mirrors _TITLES in app/services/deliverable_service.py.
var docTitles = map[string]string{
	"investment_memo": "Investment Memo",
	"ic_presentation": "IC Presentation",
	"financial_model": "Financial Model",
}

// deliverableSystemPrompt ports _DELIVERABLE_SYSTEM_PROMPT (the /chat side-panel).
const deliverableSystemPrompt = "You are an expert AI assistant for investment banking and private equity " +
	"professionals. You help create deal deliverables — investment memos, " +
	"financial models, IC presentations, and other deal documents. You have " +
	"deep expertise in financial analysis, valuation, market research, and " +
	"professional document structuring.\n\n" +
	"When the user describes a deliverable they want, help them refine the " +
	"scope, suggest sections and structure, ask clarifying questions about " +
	"audience and emphasis, and provide substantive content guidance. Be " +
	"concise, professional, and actionable.\n\n" +
	"Always respond in a helpful, structured way using markdown formatting " +
	"where appropriate."

// RegisterDeliverables mounts the deal-scoped deliverable routes. Both are
// session-authed and deal-scoped (the parent group already applies requireAuth,
// but this Register func is also safe to mount on a bare router because it wraps
// itself in requireAuth). Flat chi patterns under the shared /deals/{dealID}
// prefix so they sit beside the other deal sub-resources.
func (s *Server) RegisterDeliverables(r chi.Router) {
	r.Group(func(r chi.Router) {
		r.Use(s.requireAuth)
		r.Post("/deals/{dealID}/deliverables/generate", s.generateDeliverable)
		r.Post("/deals/{dealID}/deliverables/chat", s.deliverableChat)
	})
}

type deliverableGenerateBody struct {
	Type string `json:"type"`
}

type deliverableChatBody struct {
	Message string `json:"message"`
}

// POST /api/v1/deals/{dealID}/deliverables/generate
func (s *Server) generateDeliverable(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	dealID := chi.URLParam(r, "dealID")

	var b deliverableGenerateBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	label, ok := typeLabels[b.Type]
	if !ok {
		writeError(w, http.StatusBadRequest, "Unsupported deliverable type: "+b.Type)
		return
	}

	// Deal-scoped: a missing/foreign deal is a 404 (ports _require_deal_access).
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, dealID); storeError(w, err) {
		return
	}

	if s.LLM == nil {
		writeError(w, http.StatusBadGateway, generateFailureDetail(label))
		return
	}

	// Gather deal context (org-scoped read of meetings/analyses/documents).
	dealContext, err := store.GatherDealContext(r.Context(), s.DB, p, dealID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, generateFailureDetail(label))
		return
	}

	systemPrompt := typePrompts[b.Type]
	if systemPrompt == "" {
		systemPrompt = typePrompts["investment_memo"]
	}
	resp, err := s.LLM.Complete(r.Context(), llm.TaskICMemo, systemPrompt,
		"Deal context:\n\n"+dealContext, llm.CompleteOpts{MaxTokens: 4096, Temperature: 0.4})
	if err != nil {
		writeError(w, http.StatusBadGateway, generateFailureDetail(label))
		return
	}
	markdown := strings.TrimSpace(resp.Content)
	if markdown == "" {
		markdown = "# Deliverable\n\n_Empty LLM response._"
	}

	docTitle := docTitles[b.Type]
	if docTitle == "" {
		docTitle = "Deliverable"
	}
	docx, err := markdownToDocx(markdown, docTitle)
	if err != nil {
		writeError(w, http.StatusInternalServerError, generateFailureDetail(label))
		return
	}

	fileKey := dealID + "/" + util.NewUUID() + ".docx"
	if err := storage.SaveBytes(s.Cfg.StorageRoot, deliverablesBucket, fileKey, docx); err != nil {
		writeError(w, http.StatusInternalServerError, generateFailureDetail(label))
		return
	}
	downloadURL := strings.TrimRight(s.Cfg.PublicAPIURL, "/") +
		storage.MakeSignedURL(s.Cfg.StorageSigningKeyOrFallback(), deliverablesBucket, fileKey, "GET", time.Hour)

	now := util.NowISO()
	out := model.Deliverable{
		ID:              util.NewUUID(),
		DealID:          dealID,
		Title:           docTitle + " - " + time.Now().UTC().Format("2006-01-02"),
		DeliverableType: b.Type,
		FileFormat:      "docx",
		FileKey:         fileKey,
		Status:          "ready",
		DownloadURL:     downloadURL,
		CreatedAt:       now,
	}
	writeJSON(w, http.StatusCreated, out)
}

// generateFailureDetail mirrors the Python 500 detail string.
func generateFailureDetail(label string) string {
	return "Failed to generate " + label + ". " +
		"The LLM or storage upload errored — try again in a moment."
}

// POST /api/v1/deals/{dealID}/deliverables/chat
func (s *Server) deliverableChat(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	dealID := chi.URLParam(r, "dealID")

	var b deliverableChatBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}

	// Deal-scoped (ports _require_deal_access).
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, dealID); storeError(w, err) {
		return
	}

	// On any LLM error the Python handler returns 200 with a fallback message
	// (never surfaces the error), so the side-panel always gets a reply.
	content := "I couldn't reach the LLM right now. Try again in a moment; " +
		"if this keeps happening, verify the Fireworks API key is set."
	if s.LLM != nil {
		if resp, err := s.LLM.Complete(r.Context(), llm.TaskGeneral, deliverableSystemPrompt,
			b.Message, llm.CompleteOpts{MaxTokens: 2048, Temperature: 0.7}); err == nil {
			content = resp.Content
		}
	}

	writeJSON(w, http.StatusOK, model.DeliverableChatMessage{
		ID:        util.NewUUID(),
		DealID:    dealID,
		Role:      "assistant",
		Content:   content,
		CreatedAt: util.NowISO(),
	})
}

// ---- minimal .docx rendering (no external dep) -----------------------------
//
// A .docx is an OOXML (Office Open XML) zip: [Content_Types].xml + _rels/.rels +
// word/document.xml (+ word/_rels/document.xml.rels). We emit a minimal valid
// package that Word/Pages/Google Docs all open. The body is built from Markdown
// with the exact line rules from _markdown_to_docx in the Python service:
//   - "# "    -> Heading1
//   - "## "   -> Heading2
//   - "### "  -> Heading3
//   - "- "/"* "-> bullet list item
//   - blank   -> empty paragraph
//   - else    -> normal paragraph
// plus a Title (Heading level-0) paragraph at the top.

func markdownToDocx(markdown, title string) ([]byte, error) {
	var body strings.Builder
	body.WriteString(paragraph("Title", title))

	for _, raw := range strings.Split(markdown, "\n") {
		line := strings.TrimRight(raw, " \t\r")
		if strings.TrimSpace(line) == "" {
			body.WriteString(paragraph("", ""))
			continue
		}
		switch {
		case strings.HasPrefix(line, "# "):
			body.WriteString(paragraph("Heading1", strings.TrimSpace(line[2:])))
		case strings.HasPrefix(line, "## "):
			body.WriteString(paragraph("Heading2", strings.TrimSpace(line[3:])))
		case strings.HasPrefix(line, "### "):
			body.WriteString(paragraph("Heading3", strings.TrimSpace(line[4:])))
		case strings.HasPrefix(line, "- "), strings.HasPrefix(line, "* "):
			body.WriteString(bulletParagraph(strings.TrimSpace(line[2:])))
		default:
			body.WriteString(paragraph("", strings.TrimSpace(line)))
		}
	}

	documentXML := xmlHeader +
		`<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
		`<w:body>` + body.String() +
		`<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>` +
		`<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>` +
		`</w:sectPr></w:body></w:document>`

	files := map[string]string{
		"[Content_Types].xml":          contentTypesXML,
		"_rels/.rels":                  rootRelsXML,
		"word/document.xml":            documentXML,
		"word/_rels/document.xml.rels": documentRelsXML,
		"word/styles.xml":              stylesXML,
	}

	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	// Deterministic file order for a stable package.
	for _, name := range []string{
		"[Content_Types].xml",
		"_rels/.rels",
		"word/document.xml",
		"word/_rels/document.xml.rels",
		"word/styles.xml",
	} {
		fw, err := zw.Create(name)
		if err != nil {
			return nil, err
		}
		if _, err := fw.Write([]byte(files[name])); err != nil {
			return nil, err
		}
	}
	if err := zw.Close(); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// paragraph emits a <w:p> with an optional named style and text run. An empty
// style means the document default (Normal). An empty text emits an empty
// paragraph (matching doc.add_paragraph("")).
func paragraph(style, text string) string {
	var b strings.Builder
	b.WriteString("<w:p>")
	if style != "" {
		b.WriteString(`<w:pPr><w:pStyle w:val="` + style + `"/></w:pPr>`)
	}
	if text != "" {
		b.WriteString("<w:r><w:t xml:space=\"preserve\">" + escapeXML(text) + "</w:t></w:r>")
	}
	b.WriteString("</w:p>")
	return b.String()
}

// bulletParagraph emits a bullet list item (ListBullet style + numbering ref).
func bulletParagraph(text string) string {
	return `<w:p><w:pPr><w:pStyle w:val="ListBullet"/>` +
		`<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>` +
		`<w:r><w:t xml:space="preserve">` + escapeXML(text) + `</w:t></w:r></w:p>`
}

func escapeXML(s string) string {
	var b bytes.Buffer
	_ = xml.EscapeText(&b, []byte(s))
	return b.String()
}

const xmlHeader = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` + "\n"

const contentTypesXML = xmlHeader +
	`<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
	`<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
	`<Default Extension="xml" ContentType="application/xml"/>` +
	`<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>` +
	`<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>` +
	`</Types>`

const rootRelsXML = xmlHeader +
	`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
	`<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>` +
	`</Relationships>`

const documentRelsXML = xmlHeader +
	`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
	`<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>` +
	`</Relationships>`

// stylesXML declares the handful of named styles the body references so Word
// renders headings/title/bullets distinctly.
const stylesXML = xmlHeader +
	`<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
	`<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>` +
	`<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="56"/></w:rPr></w:style>` +
	`<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>` +
	`<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>` +
	`<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>` +
	`<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/></w:style>` +
	`</w:styles>`
