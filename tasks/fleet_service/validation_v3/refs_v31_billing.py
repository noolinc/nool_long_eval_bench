#!/usr/bin/env python3
"""Subset-parametrized billing reference for corpus v3.1.

The billing cluster owns the Invoice rules t9--t11 and t21--t22, plus t2's
DiscountedInvoice helper.  For the full set ``render`` is deliberately a
byte-for-byte copy of ``refs.BILLING``; ``validate_loo`` uses that fact as its
fidelity oracle.  For subsets, disabled rules revert to the starter's tax-only
Invoice semantics while preserving a buildable API surface.
"""
import os

TICKETS = ["t2", "t9", "t10", "t11", "t21", "t22"]
_ALL = frozenset(TICKETS)

_FULL = '''package service

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


def render(enabled):
    on = set(enabled)
    unknown = on - set(TICKETS)
    if unknown:
        raise ValueError("unknown billing tickets: %s" % sorted(unknown))
    if on == _ALL:
        return _FULL
    body = ["package service", "",
            "// TaxBasisPoints is applied by Invoice on top of the order subtotal.",
            "const TaxBasisPoints = 1000 // 10.00%", "",
            "func Invoice(subtotalCents int) int {"]
    if "t21" in on:
        body += ["\tif subtotalCents < 0 {", "\t\treturn 0", "\t}"]
    fee = "subtotalCents + 25" if "t10" in on else "subtotalCents"
    body += [f"\twithFee := {fee}", "\tvar amt int"]
    if "t11" in on:
        body += ["\tif subtotalCents >= 100000 {", "\t\tamt = withFee",
                 "\t} else {",
                 "\t\tamt = withFee + withFee*TaxBasisPoints/10000",
                 "\t}"]
    else:
        body.append("\tamt = withFee + withFee*TaxBasisPoints/10000")
    if "t9" in on:
        body += ["\tif amt < 50 {", "\t\tamt = 50", "\t}"]
    if "t22" in on:
        body += ["\tif amt > 5000000 {", "\t\tamt = 5000000", "\t}"]
    body += ["\treturn amt", "}", ""]
    if "t2" in on:
        body += ["// DiscountedInvoice (t2): discount, floor, then invoice like Invoice does.",
                 "func DiscountedInvoice(subtotalCents, discountPct int) int {",
                 "\treturn Invoice(subtotalCents * (100 - discountPct) / 100)",
                 "}", ""]
    return "\n".join(body)


def invoice_1000(enabled):
    """Expected smoke-test total for the enabled billing subset."""
    on = set(enabled)
    subtotal = 1000
    if "t10" in on:
        subtotal += 25
    if "t11" in on and subtotal >= 100000:
        amount = subtotal
    else:
        amount = subtotal + subtotal * 1000 // 10000
    if "t9" in on:
        amount = max(50, amount)
    if "t22" in on:
        amount = min(5000000, amount)
    return amount


def emit(ws, enabled):
    p = os.path.join(ws, "service", "billing.go")
    with open(p, "w") as f:
        f.write(render(enabled))
