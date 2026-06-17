// Package llm ports the task→model router (app/llm/router.py) and the Fireworks
// provider (app/llm/fireworks_provider.py): chat completions + nomic embeddings,
// with the same task routing, env overrides, retry, and concurrency caps.
package llm

import (
	"fmt"
	"os"
	"strings"
)

// Canonical task names (match app/llm/router.py).
const (
	TaskSummarization = "summarization"
	TaskActionItems   = "action_items"
	TaskQARAG         = "qa_rag"
	TaskQAMeeting     = "qa_meeting"
	TaskICMemo        = "ic_memo"
	TaskGeneral       = "general"
	TaskEmbedding     = "embedding"
)

const (
	fireworksGLM      = "fireworks:accounts/fireworks/models/glm-5p1"
	fireworksDeepSeek = "fireworks:accounts/fireworks/models/deepseek-v4-pro"
	fireworksNomic    = "fireworks:nomic-ai/nomic-embed-text-v1.5"
)

var defaultTaskModel = map[string]string{
	TaskSummarization: fireworksGLM,
	TaskActionItems:   fireworksGLM,
	TaskQARAG:         fireworksDeepSeek,
	TaskQAMeeting:     fireworksGLM,
	TaskICMemo:        fireworksDeepSeek,
	TaskGeneral:       fireworksGLM,
	TaskEmbedding:     fireworksNomic,
}

var envOverrideKey = map[string]string{
	TaskSummarization: "LLM_MODEL_FOR_SUMMARIZATION",
	TaskActionItems:   "LLM_MODEL_FOR_ACTION_ITEMS",
	TaskQARAG:         "LLM_MODEL_FOR_QA_RAG",
	TaskQAMeeting:     "LLM_MODEL_FOR_QA_MEETING",
	TaskICMemo:        "LLM_MODEL_FOR_IC_MEMO",
	TaskGeneral:       "LLM_MODEL_FOR_GENERAL",
	TaskEmbedding:     "LLM_MODEL_FOR_EMBEDDING",
}

// resolveModel returns (provider, model) for a task, honouring the
// LLM_MODEL_FOR_<TASK> env override (ports _resolve_model).
func resolveModel(task string) (provider, model string, err error) {
	spec := ""
	if k := envOverrideKey[task]; k != "" {
		spec = os.Getenv(k)
	}
	if spec == "" {
		spec = defaultTaskModel[task]
	}
	if spec == "" {
		spec = defaultTaskModel[TaskGeneral]
	}
	p, m, ok := strings.Cut(spec, ":")
	if !ok {
		return "", "", fmt.Errorf("invalid model spec for %s: %q (expected '<provider>:<model>')", task, spec)
	}
	return strings.TrimSpace(p), strings.TrimSpace(m), nil
}

func premiumEnabled() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("PREMIUM_LLM_ENABLED"))) {
	case "1", "true", "yes":
		return true
	default:
		return false
	}
}
