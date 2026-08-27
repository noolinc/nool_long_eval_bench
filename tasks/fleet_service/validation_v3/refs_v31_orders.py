#!/usr/bin/env python3
"""Subset-parametrized reference generator for the orders cluster (corpus v3.1).

refs.apply_orders writes monolithic replacement files implementing all five
orders tickets at once, which makes within-cluster leave-one-out validation
inexpressible (the documented limit in validate_negative.py). This module
re-derives the same files from an arbitrary subset of the orders tickets.

Contract:
  * emit(ws, enabled) replaces refs.apply_orders in the canonical
    refs.apply_all order (billing, users, orders, store, api, ids, clock,
    fillers). It assumes refs.apply_billing and refs.apply_users have
    already run (validate_negative.REQUIRES = {"orders": {"billing",
    "users"}}): DiscountedInvoice and ErrNotFound therefore exist, and
    t2's TotalWithDiscount — appended to service/orders.go by
    apply_billing — is preserved in every emitted service/orders.go.
  * emit(ws, set(TICKETS)) produces the same orders/model/audit output as
    refs.apply_orders(ws). Billing is deliberately left untouched: the
    billing subset generator ran earlier, and rewriting it here would make
    every billing LOO variant silently regain all disabled billing tickets.
  * Disabled tickets revert to starter semantics (t5 disabled also removes
    util/audit.go, which the starter does not have); every subset compiles
    and is gofmt-clean given the billing+users precondition.
"""
import os

TICKETS = ["t2", "t5", "t18", "t30", "t31", "t32"]

# Verbatim copy of refs.BILLING (apply_orders rewrites service/billing.go
# because TotalWithDiscount depends on DiscountedInvoice).
_BILLING = '''package service

// TaxBasisPoints is applied by Invoice on top of the order subtotal.
const TaxBasisPoints = 1000 // 10.00%

// Invoice: negative subtotals are rejected with zero (t21); a 25c processing fee is
// added before tax (t10); subtotals >= 100000 pay no tax (t11); the result
// is at least 50 (t9) and at most 5000000, cap applied last (t22).
func Invoice(subtotalCents int) int {
	if subtotalCents < 0 {
		return 0
	}
	withFee := subtotalCents + 25
	var amt int
	if subtotalCents >= 100000 {
		amt = withFee
	} else {
		amt = withFee + withFee*TaxBasisPoints/10000
	}
	if amt < 50 {
		amt = 50
	}
	if amt > 5000000 {
		amt = 5000000
	}
	return amt
}

// DiscountedInvoice (t2): discount, floor, then invoice like Invoice does.
func DiscountedInvoice(subtotalCents, discountPct int) int {
	return Invoice(subtotalCents * (100 - discountPct) / 100)
}
'''

# Verbatim copy of refs.AUDIT (t5).
_AUDIT = '''package util

import "sync"

var (
	auditMu  sync.Mutex
	auditLog []string
)

// Audit (t5): append-only event record.
func Audit(event string) {
	auditMu.Lock()
	defer auditMu.Unlock()
	auditLog = append(auditLog, event)
}

func AuditLog() []string {
	auditMu.Lock()
	defer auditMu.Unlock()
	out := make([]string, len(auditLog))
	copy(out, auditLog)
	return out
}
'''


def _W(ws, rel, content):
    p = os.path.join(ws, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)


def _model_order(en):
    """model/order.go with gofmt field/comment alignment per subset."""
    fields = [("ID", "string", None), ("UserID", "string", None),
              ("Cents", "int", None)]
    if "t18" in en:
        fields.append(("Status", "string", "t18"))
    if "t31" in en:
        fields.append(("CreatedAt", "int64", "t31"))
    name_w = max(len(n) for n, _, _ in fields)
    type_w = max((len(t) for _, t, c in fields if c), default=0)
    lines = []
    for n, t, c in fields:
        if c:
            lines.append("\t%s %s // %s" % (n.ljust(name_w), t.ljust(type_w), c))
        else:
            lines.append("\t%s %s" % (n.ljust(name_w), t))
    return ("package model\n\ntype Order struct {\n"
            + "\n".join(lines) + "\n}\n")


def _orders_go(en):
    """service/orders.go implementing exactly `en`; starter semantics else."""
    src = ["package service", "", "import (", '\t"encoding/json"']
    if "t30" in en:
        src.append('\t"errors"')
    src += ["", '\t"bench/fleetsvc/model"', '\t"bench/fleetsvc/store"',
            '\t"bench/fleetsvc/util"', ")", "",
            "type Orders struct {", "\tS store.KV", "}", ""]

    src.append("func (o *Orders) Create(userID string, cents int) (*model.Order, error) {")
    if "t30" in en:
        src += ["\tif cents <= 0 { // t30",
                '\t\treturn nil, errors.New("non-positive amount")', "\t}"]
    lit = '\tord := &model.Order{ID: util.NewID("order"), UserID: userID, Cents: cents'
    if "t31" in en:
        src.append(lit + ", CreatedAt: util.Now()} // t31")
    else:
        src.append(lit + "}")
    src += ["\tb, err := json.Marshal(ord)", "\tif err != nil {",
            "\t\treturn nil, err", "\t}", '\to.S.Put("order/"+ord.ID, b)']
    if "t5" in en:
        src.append('\tutil.Audit("order.created " + ord.ID) // t5')
    src += ["\treturn ord, nil", "}", ""]

    src += ["func (o *Orders) Get(id string) (*model.Order, error) {",
            '\tb, ok := o.S.Get("order/" + id)', "\tif !ok {",
            "\t\treturn nil, ErrNotFound", "\t}", "\tvar ord model.Order",
            "\tif err := json.Unmarshal(b, &ord); err != nil {",
            "\t\treturn nil, err", "\t}", "\treturn &ord, nil", "}", ""]

    if "t18" in en:
        src += ["// SetStatus (t18).",
                "func (o *Orders) SetStatus(id, status string) error {",
                "\tord, err := o.Get(id)", "\tif err != nil {",
                "\t\treturn err", "\t}", "\tord.Status = status",
                "\tb, err := json.Marshal(ord)", "\tif err != nil {",
                "\t\treturn err", "\t}", '\to.S.Put("order/"+ord.ID, b)',
                "\treturn nil", "}", ""]

    if "t32" in en:
        src.append("// TotalFor sums positive-cents orders for a user (t32 ignores the rest).")
        cond = "if json.Unmarshal(b, &ord) == nil && ord.UserID == userID && ord.Cents > 0 {"
    else:
        src.append("// TotalFor sums cents across a user's orders.")
        cond = "if json.Unmarshal(b, &ord) == nil && ord.UserID == userID {"
    src += ["func (o *Orders) TotalFor(userID string) int {", "\ttotal := 0",
            '\tfor _, k := range o.S.Keys("order/") {',
            "\t\tb, ok := o.S.Get(k)", "\t\tif !ok {", "\t\t\tcontinue",
            "\t\t}", "\t\tvar ord model.Order", "\t\t" + cond,
            "\t\t\ttotal += ord.Cents", "\t\t}", "\t}", "\treturn total",
            "}", ""]

    if "t2" in en:
        src += ["// TotalWithDiscount (t2).",
                "func (o *Orders) TotalWithDiscount(userID string, discountPct int) int {",
                "\treturn DiscountedInvoice(o.TotalFor(userID), discountPct)", "}"]
    return "\n".join(src) + "\n"


def emit(ws, enabled):
    """Write orders-cluster files implementing exactly `enabled`."""
    en = set(enabled)
    unknown = en - set(TICKETS)
    if unknown:
        raise ValueError("unknown orders tickets: %s" % sorted(unknown))
    _W(ws, "service/orders.go", _orders_go(en))
    _W(ws, "model/order.go", _model_order(en))
    if "t5" in en:
        _W(ws, "util/audit.go", _AUDIT)
    else:
        p = os.path.join(ws, "util/audit.go")
        if os.path.exists(p):
            os.remove(p)
    # Do not rewrite service/billing.go here. refs_v31_billing emitted the
    # requested subset earlier in the canonical composition order.
