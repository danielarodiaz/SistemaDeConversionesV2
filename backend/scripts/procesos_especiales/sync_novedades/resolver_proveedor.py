from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import Proveedor, SyncNovedadesProveedorMatch

from .modelos import ProveedorResuelto
from .normalizacion import normalize_text


try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None


class ProveedorResolver:
    def __init__(self, db: Session, threshold: int = 90):
        self.db = db
        self.threshold = threshold
        self.proveedores = db.query(Proveedor).all()
        self.by_normalized = {}
        for proveedor in self.proveedores:
            if not proveedor.cod_prov or not proveedor.razon_social:
                continue
            key = normalize_text(proveedor.razon_social)
            if key:
                self.by_normalized.setdefault(key, []).append(proveedor)

    def resolve(self, origen: str) -> tuple[ProveedorResuelto | None, dict | None]:
        normalized = normalize_text(origen)
        exact = self.by_normalized.get(normalized, [])
        if len(exact) == 1:
            return self._as_resuelto(exact[0], "EXACT", 100), None
        if len(exact) > 1:
            return None, {"reason": "proveedor_duplicado", "detail": f"{len(exact)} proveedores con razon social normalizada igual"}

        if process is None or fuzz is None:
            return None, {"reason": "rapidfuzz_no_instalado", "detail": "Instalar rapidfuzz para matching difuso"}

        choices = list(self.by_normalized.keys())
        if not normalized or not choices:
            return None, {"reason": "proveedor_sin_resolver", "detail": "Origen vacio o tabla proveedores vacia"}

        scored_matches = self._scored_matches(normalized, choices)
        if not scored_matches:
            return None, {"reason": "proveedor_sin_resolver", "detail": "Sin candidatos"}

        matched_key, score, coverage, token_set, partial = scored_matches[0]
        second_score = scored_matches[1][1] if len(scored_matches) > 1 else 0
        winner_margin = score - second_score
        accepted_by_score = score >= self.threshold
        accepted_by_coverage = coverage >= 0.50 and token_set >= 90 and partial >= 90 and score >= (self.threshold - 10)
        accepted_by_clear_winner = (
            len(matched_key.split()) >= 2
            and score >= (self.threshold - 8)
            and winner_margin >= 10
        )
        if not (accepted_by_score or accepted_by_coverage or accepted_by_clear_winner):
            # TODO: Definir umbral final de fuzzy matching segun los primeros resultados reales.
            candidates_detail = "; ".join(
                f"{key}: {candidate_score:.2f}" for key, candidate_score, _, _, _ in scored_matches[:5]
            )
            return None, {
                "reason": "proveedor_sin_resolver",
                "detail": f"Mejores candidatos fuzzy: {candidates_detail}",
            }

        candidates = self.by_normalized[matched_key]
        if len(candidates) != 1:
            return None, {"reason": "proveedor_duplicado", "detail": f"{len(candidates)} candidatos fuzzy para {matched_key}"}

        proveedor = candidates[0]
        self._audit_fuzzy(origen, normalized, proveedor, score)
        return self._as_resuelto(proveedor, "FUZZY", float(score)), {
            "origen_original": origen,
            "origen_normalizado": normalized,
            "cod_prov": proveedor.cod_prov,
            "razon_social": proveedor.razon_social,
            "score": float(score),
            "winner_margin": float(winner_margin),
        }

    def _as_resuelto(self, proveedor: Proveedor, metodo: str, score: float) -> ProveedorResuelto:
        return ProveedorResuelto(
            id=proveedor.id,
            cod_prov=proveedor.cod_prov or "",
            razon_social=proveedor.razon_social or "",
            marca=proveedor.marca or "",
            pivot=proveedor.pivot or "",
            tipo=proveedor.tipo or "",
            metodo=metodo,
            score=score,
        )

    def _audit_fuzzy(self, origen: str, normalized: str, proveedor: Proveedor, score: float) -> None:
        origen = _limit(origen, 255)
        normalized = _limit(normalized, 255)
        cod_prov = _limit(proveedor.cod_prov or "", 50)
        razon_social = _limit(proveedor.razon_social or "", 255)
        audit = (
            self.db.query(SyncNovedadesProveedorMatch)
            .filter(
                SyncNovedadesProveedorMatch.origen_normalizado == normalized,
                SyncNovedadesProveedorMatch.proveedor_id == proveedor.id,
            )
            .first()
        )
        if audit:
            audit.origen_original = origen
            audit.cod_prov = cod_prov
            audit.razon_social = razon_social
            audit.score = max(float(audit.score or 0), float(score))
            return

        self.db.add(
            SyncNovedadesProveedorMatch(
                origen_original=origen,
                origen_normalizado=normalized,
                proveedor_id=proveedor.id,
                cod_prov=cod_prov,
                razon_social=razon_social,
                score=score,
                metodo="FUZZY",
            )
        )
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            audit = (
                self.db.query(SyncNovedadesProveedorMatch)
                .filter(
                    SyncNovedadesProveedorMatch.origen_normalizado == normalized,
                    SyncNovedadesProveedorMatch.proveedor_id == proveedor.id,
                )
                .first()
            )
            if audit:
                audit.origen_original = origen
                audit.cod_prov = cod_prov
                audit.razon_social = razon_social
                audit.score = max(float(audit.score or 0), float(score))

    def _scored_matches(self, normalized: str, choices: list[str]) -> list[tuple[str, float, float, float, float]]:
        scored = []
        for choice in choices:
            wratio = fuzz.WRatio(normalized, choice)
            partial = fuzz.partial_ratio(normalized, choice)
            token_set = fuzz.token_set_ratio(normalized, choice)
            coverage = _origin_token_coverage(normalized, choice)
            single_token_penalty = 0.65 if len(choice.split()) == 1 and len(normalized.split()) > 1 else 1.0
            score = (
                wratio * 0.40
                + partial * 0.25
                + token_set * 0.15
                + coverage * 100 * 0.20
            ) * single_token_penalty
            scored.append((choice, float(score), float(coverage), float(token_set), float(partial)))
        return sorted(scored, key=lambda item: item[1], reverse=True)


def _origin_token_coverage(origin: str, candidate: str) -> float:
    origin_tokens = [token for token in origin.split() if len(token) > 1]
    candidate_tokens = [token for token in candidate.split() if len(token) > 1]
    if not origin_tokens:
        return 0.0
    matched = 0
    for origin_token in origin_tokens:
        if any(_tokens_match(origin_token, candidate_token) for candidate_token in candidate_tokens):
            matched += 1
    return matched / len(origin_tokens)


def _tokens_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if left.rstrip("S") == right.rstrip("S"):
        return True
    return fuzz.ratio(left, right) >= 85


def _limit(value: str, max_length: int) -> str:
    return (value or "")[:max_length]
