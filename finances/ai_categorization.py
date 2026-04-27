import json
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class CategorySuggestion:
    """
    Represents a category suggestion returned by rules or AI.
    """

    category: Any | None
    subcategory: Any | None
    confidence: Decimal
    reason: str
    source: str


def normalize_text(value):
    """
    Normalize text for local rule matching.
    """
    if not value:
        return ""

    return value.strip().lower()


def get_available_categories(company, movement_type):
    """
    Return active categories and subcategories for a movement type.
    """
    from finances.models import FinancialCategory

    return FinancialCategory.objects.filter(
        company=company,
        movement_type=movement_type,
        is_active=True,
    ).prefetch_related(
        "subcategories",
    )


def suggest_by_local_rules(company, description, movement_type):
    """
    Suggest a category using deterministic local keyword rules.
    """
    from finances.models import FinancialMovement

    normalized_description = normalize_text(description)

    if not normalized_description:
        return None

    categories = get_available_categories(
        company=company,
        movement_type=movement_type,
    )

    for category in categories:
        category_name = normalize_text(category.name)

        if category_name and category_name in normalized_description:
            return CategorySuggestion(
                category=category,
                subcategory=None,
                confidence=Decimal("0.80"),
                reason="Matched category name in transaction description.",
                source="rules",
            )

        for subcategory in category.subcategories.filter(is_active=True):
            subcategory_name = normalize_text(subcategory.name)

            if subcategory_name and subcategory_name in normalized_description:
                return CategorySuggestion(
                    category=category,
                    subcategory=subcategory,
                    confidence=Decimal("0.90"),
                    reason="Matched subcategory name in transaction description.",
                    source="rules",
                )

    keyword_map = {
        FinancialMovement.MovementType.EXPENSE: {
            "comiss": "Comissões",
            "gest": "Comissões",
            "pag.serv": "Serviços",
            "tsu": "Impostos",
            "orden": "Salários",
            "salario": "Salários",
            "salário": "Salários",
            "fornec": "Fornecedores",
            "levantamento": "Caixa",
            "cartao": "Cartão",
            "cartão": "Cartão",
        },
        FinancialMovement.MovementType.INCOME: {
            "transf software": "Receitas operacionais",
            "orden. age": "Receitas operacionais",
            "transf": "Transferências recebidas",
        },
    }

    for keyword, category_name in keyword_map.get(movement_type, {}).items():
        if keyword in normalized_description:
            category = categories.filter(
                name__iexact=category_name,
            ).first()

            if category:
                return CategorySuggestion(
                    category=category,
                    subcategory=None,
                    confidence=Decimal("0.75"),
                    reason=f"Matched local keyword rule: {keyword}.",
                    source="rules",
                )

    return None


def build_ai_prompt(company, description, movement_type, amount, categories):
    """
    Build prompt payload for AI categorization.
    """
    category_payload = []

    for category in categories:
        subcategories = []

        for subcategory in category.subcategories.filter(is_active=True):
            subcategories.append(
                {
                    "id": subcategory.id,
                    "name": subcategory.name,
                }
            )

        category_payload.append(
            {
                "id": category.id,
                "name": category.name,
                "subcategories": subcategories,
            }
        )

    return {
        "company": company.name,
        "movement_type": movement_type,
        "amount": str(amount),
        "description": description,
        "available_categories": category_payload,
        "instructions": (
            "Choose the best category and optional subcategory for this bank "
            "transaction. Only choose from available_categories. "
            "Return JSON only with category_id, subcategory_id, confidence and reason. "
            "If unsure, return null ids and low confidence."
        ),
    }


def call_openai_for_category_suggestion(company, description, movement_type, amount):
    """
    Ask OpenAI for a category suggestion.

    If OpenAI is not configured or fails, return None without breaking import.
    """
    from finances.models import FinancialSubcategory

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None

    categories = get_available_categories(
        company=company,
        movement_type=movement_type,
    )

    if not categories.exists():
        return None

    prompt_payload = build_ai_prompt(
        company=company,
        description=description,
        movement_type=movement_type,
        amount=amount,
        categories=categories,
    )

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
        )

        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_CATEGORY_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a financial transaction categorization assistant. "
                        "You must return strict JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        prompt_payload,
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={
                "type": "json_object",
            },
            temperature=0,
        )

        content = completion.choices[0].message.content

        if not content:
            return None

        data = json.loads(content)

        category_id = data.get("category_id")
        subcategory_id = data.get("subcategory_id")
        confidence = Decimal(str(data.get("confidence", "0.00")))
        reason = data.get("reason", "AI categorization suggestion.")

        category = None
        subcategory = None

        if category_id:
            category = categories.filter(
                id=category_id,
            ).first()

        if subcategory_id and category:
            subcategory = FinancialSubcategory.objects.filter(
                id=subcategory_id,
                company=company,
                category=category,
                is_active=True,
            ).first()

        if not category:
            return None

        return CategorySuggestion(
            category=category,
            subcategory=subcategory,
            confidence=confidence,
            reason=reason,
            source="ai",
        )

    except Exception:
        logger.exception("AI categorization failed.")
        return None


def suggest_category_for_transaction(company, description, movement_type, amount):
    """
    Suggest category for a transaction.

    Priority:
    1. deterministic local rules;
    2. AI suggestion;
    3. None.
    """
    local_suggestion = suggest_by_local_rules(
        company=company,
        description=description,
        movement_type=movement_type,
    )

    if local_suggestion:
        return local_suggestion

    return call_openai_for_category_suggestion(
        company=company,
        description=description,
        movement_type=movement_type,
        amount=amount,
    )