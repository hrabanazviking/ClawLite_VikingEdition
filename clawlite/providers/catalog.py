from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProviderProfile:
    family: str
    recommended_models: tuple[str, ...]
    onboarding_hint: str


ONBOARDING_PROVIDER_ORDER: tuple[str, ...] = (
    "openai",
    "anthropic",
    "gemini",
    "groq",
    "deepseek",
    "openrouter",
    "xai",
    "mistral",
    "moonshot",
    "zai",
    "qianfan",
    "huggingface",
    "together",
    "kilocode",
    "minimax",
    "xiaomi",
    "kimi-coding",
    "ollama",
    "vllm",
)


PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    "custom": ProviderProfile(
        family="custom",
        recommended_models=(),
        onboarding_hint="Provider customizado; revise manualmente modelo, auth e base URL antes de usar.",
    ),
    "openrouter": ProviderProfile(
        family="gateway",
        recommended_models=("openrouter/auto", "openrouter/openai/gpt-4o-mini"),
        onboarding_hint="Gateway multi-model; o modo 'auto' nao exige match exato na lista remota.",
    ),
    "kilocode": ProviderProfile(
        family="gateway",
        recommended_models=("kilocode/anthropic/claude-opus-4.6",),
        onboarding_hint="Gateway multi-model; confirme o provider upstream embutido no nome do modelo.",
    ),
    "gemini": ProviderProfile(
        family="openai_compatible",
        recommended_models=("gemini/gemini-2.5-flash", "gemini/gemini-2.5-pro"),
        onboarding_hint="Gemini usa endpoint OpenAI-compatible via Google Generative Language.",
    ),
    "groq": ProviderProfile(
        family="openai_compatible",
        recommended_models=("groq/llama-3.1-8b-instant", "groq/llama-3.3-70b-versatile"),
        onboarding_hint="Groq responde via OpenAI-compatible; priorize modelos latentes de baixa latencia.",
    ),
    "deepseek": ProviderProfile(
        family="openai_compatible",
        recommended_models=("deepseek/deepseek-chat", "deepseek/deepseek-reasoner"),
        onboarding_hint="DeepSeek responde via OpenAI-compatible; valide quota e billing antes do rollout.",
    ),
    "together": ProviderProfile(
        family="gateway",
        recommended_models=("together/moonshotai/Kimi-K2.5", "together/meta-llama/Llama-3.3-70B-Instruct-Turbo"),
        onboarding_hint="Together funciona como gateway OpenAI-compatible; confirme o nome completo do upstream.",
    ),
    "huggingface": ProviderProfile(
        family="gateway",
        recommended_models=("huggingface/deepseek-ai/DeepSeek-R1", "huggingface/meta-llama/Llama-3.3-70B-Instruct"),
        onboarding_hint="Hugging Face router expõe modelos upstream completos; confirme o repo/model id.",
    ),
    "xai": ProviderProfile(
        family="openai_compatible",
        recommended_models=("xai/grok-4", "xai/grok-4-fast-reasoning"),
        onboarding_hint="xAI responde via OpenAI-compatible; confirme permissao para o modelo Grok escolhido.",
    ),
    "mistral": ProviderProfile(
        family="openai_compatible",
        recommended_models=("mistral/mistral-large-latest", "mistral/codestral-latest"),
        onboarding_hint="Mistral responde via OpenAI-compatible; prefira aliases 'latest' para evitar drift de versão fixa.",
    ),
    "moonshot": ProviderProfile(
        family="openai_compatible",
        recommended_models=("moonshot/kimi-k2.5",),
        onboarding_hint="Moonshot/Kimi responde via OpenAI-compatible; confirme disponibilidade regional do endpoint.",
    ),
    "qianfan": ProviderProfile(
        family="openai_compatible",
        recommended_models=("qianfan/deepseek-v3.2", "qianfan/ernie-4.0-turbo"),
        onboarding_hint="Qianfan usa endpoint próprio OpenAI-compatible; verifique credenciais e região Baidu Cloud.",
    ),
    "zai": ProviderProfile(
        family="openai_compatible",
        recommended_models=("zai/glm-5", "zai/glm-4.6"),
        onboarding_hint="Z.AI/GLM responde via endpoint compatível; confirme a conta habilitada para o modelo GLM.",
    ),
    "nvidia": ProviderProfile(
        family="openai_compatible",
        recommended_models=("nvidia/meta/llama-3.1-70b-instruct",),
        onboarding_hint="NVIDIA NIM responde via OpenAI-compatible; o catálogo pode variar por tenant/projeto.",
    ),
    "byteplus": ProviderProfile(
        family="openai_compatible",
        recommended_models=("byteplus/deepseek-v3.1",),
        onboarding_hint="BytePlus Ark responde via OpenAI-compatible; confirme projeto e endpoint regional.",
    ),
    "doubao": ProviderProfile(
        family="openai_compatible",
        recommended_models=("doubao/doubao-seed-1-6",),
        onboarding_hint="Doubao Ark responde via OpenAI-compatible; confirme se o tenant tem acesso ao modelo escolhido.",
    ),
    "volcengine": ProviderProfile(
        family="openai_compatible",
        recommended_models=("volcengine/doubao-seed-1-6",),
        onboarding_hint="Volcengine Ark responde via OpenAI-compatible; valide região e projeto antes do uso.",
    ),
    "minimax": ProviderProfile(
        family="anthropic_compatible",
        recommended_models=("minimax/MiniMax-M2.5",),
        onboarding_hint="MiniMax usa transporte Anthropic-compatible; a base URL costuma terminar em /anthropic.",
    ),
    "xiaomi": ProviderProfile(
        family="anthropic_compatible",
        recommended_models=("xiaomi/mimo-v2-flash",),
        onboarding_hint="Xiaomi Mimo usa transporte Anthropic-compatible; confirme base URL com sufixo /anthropic.",
    ),
    "kimi_coding": ProviderProfile(
        family="anthropic_compatible",
        recommended_models=("kimi-coding/k2p5",),
        onboarding_hint="Kimi Coding usa transporte Anthropic-compatible e base dedicada em /coding/.",
    ),
    "anthropic": ProviderProfile(
        family="anthropic_compatible",
        recommended_models=("anthropic/claude-3-5-haiku-latest", "anthropic/claude-3-7-sonnet-latest"),
        onboarding_hint="Anthropic usa transporte nativo /v1/messages; confirme a chave ANTHROPIC_API_KEY.",
    ),
    "openai": ProviderProfile(
        family="openai_compatible",
        recommended_models=("openai/gpt-4o-mini", "openai/gpt-4.1-mini"),
        onboarding_hint="OpenAI responde via endpoint OpenAI-compatible padrão; valide billing e projeto ativo.",
    ),
    "openai_codex": ProviderProfile(
        family="oauth",
        recommended_models=("openai-codex/gpt-5.3-codex",),
        onboarding_hint="OpenAI Codex usa OAuth local; faça login antes de validar o provider.",
    ),
    "ollama": ProviderProfile(
        family="local_runtime",
        recommended_models=("openai/llama3.2", "openai/qwen2.5-coder:7b"),
        onboarding_hint="Ollama exige runtime local ativo e modelo previamente baixado com 'ollama pull'.",
    ),
    "vllm": ProviderProfile(
        family="local_runtime",
        recommended_models=("vllm/meta-llama/Llama-3.2-3B-Instruct",),
        onboarding_hint="vLLM exige servidor ativo e modelo carregado no startup do processo.",
    ),
}


def provider_profile(name: str) -> ProviderProfile:
    provider_name = str(name or "").strip().lower().replace("-", "_")
    return PROVIDER_PROFILES.get(
        provider_name,
        ProviderProfile(
            family="custom",
            recommended_models=(),
            onboarding_hint="Provider sem perfil conhecido; revise manualmente modelo, auth e endpoint.",
        ),
    )


def default_provider_model(name: str) -> str:
    profile = provider_profile(name)
    return str(profile.recommended_models[0] if profile.recommended_models else "")
