"""Ten-point papers with explicit section budgets and relative item weights."""
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

KINDS = {'single': 'Trắc nghiệm', 'true_false': 'Đúng/Sai', 'short_answer': 'Trả lời ngắn'}


def kind_of(value):
    return 'true_false' if value == 'truefalse' else value


def number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Điểm phải là số hợp lệ.') from None
    if not result.is_finite() or result < 0 or result > 100:
        raise ValueError('Điểm phải là số hữu hạn từ 0 đến 100.')
    return result


def distribute(weights, total):
    """Largest remainder at 0.0001 point precision; no cumulative rounding drift."""
    units = int(total * 10000)
    shares = [Decimal(units) * weight / sum(weights) for weight in weights]
    allocated = [int(share.to_integral_value(rounding=ROUND_FLOOR)) for share in shares]
    order = sorted(range(len(shares)), key=lambda i: (-(shares[i] - allocated[i]), i))
    for i in order[:units - sum(allocated)]:
        allocated[i] += 1
    if any(value == 0 for value in allocated):
        raise ValueError('Điểm phân bổ quá nhỏ; tăng điểm phần hoặc giảm số câu/trọng số chênh lệch.')
    return [Decimal(value) / 10000 for value in allocated]


def allocate(questions, budgets=None):
    if not questions:
        raise ValueError('Đề phải có ít nhất một câu hỏi.')
    groups = {kind: [] for kind in KINDS}
    for q in questions:
        kind = kind_of(q['question_type'])
        if kind not in groups:
            raise ValueError('Hình thức câu hỏi chưa được hỗ trợ chấm điểm.')
        q['question_type'] = kind
        weight = number(q.get('weight', q.get('points', 1)))
        if weight <= 0:
            raise ValueError('Trọng số câu hỏi phải lớn hơn 0.')
        q['weight'] = float(weight)
        groups[kind].append(q)
    if budgets is None:
        points = distribute([number(q['weight']) for q in questions], Decimal(10))
        for q, point in zip(questions, points):
            q['points'] = float(point)
    else:
        amounts = {kind: number(budgets.get(kind, 0)) for kind in KINDS}
        if sum(amounts.values()) != 10:
            raise ValueError('Tổng điểm các phần phải bằng 10 điểm.')
        for kind, items in groups.items():
            amount = amounts[kind]
            if (bool(items) != bool(amount)) or amount.as_tuple().exponent < -2:
                raise ValueError(f'{KINDS[kind]}: phần có câu phải có điểm, phần không có câu phải bằng 0; dùng tối đa hai chữ số thập phân.')
            if items:
                for q, point in zip(items, distribute([number(q['weight']) for q in items], amount)):
                    q['points'] = float(point)
    return {kind: float(sum(number(q['points']) for q in items)) for kind, items in groups.items()}


def section_defaults(questions):
    """Return counts and editable budgets, rounded to cents with an exact total of 10."""
    groups = {kind: [] for kind in KINDS}
    for question in questions:
        kind = kind_of(question['question_type'])
        if kind in groups:
            groups[kind].append(question)
    counts = {kind: len(items) for kind, items in groups.items()}
    defaults = dict.fromkeys(KINDS, 0)
    active = [kind for kind, items in groups.items() if items]
    if active:
        weights = [
            sum(number(question.get('points', 1) or 1) for question in groups[kind])
            for kind in active
        ]
        # distribute uses 10,000 units/point; scaling by 100 gives cent precision.
        shares = distribute(weights, Decimal('0.1'))
        defaults.update({kind: float(share * 100) for kind, share in zip(active, shares)})
    return counts, defaults
