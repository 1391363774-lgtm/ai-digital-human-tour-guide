"""Match existing route presets; no invented stops, travel times or live facts."""
import re


def is_route_question(query):
    return bool(re.search(r'路线|游线|行程|怎么玩|怎么游|游玩安排|游览计划', query))


def uses_route_catalog(query):
    # Current presets cover Lingshan daytime visits, not Nianhua/night plans.
    return is_route_question(query) and not re.search(r'拈花湾|夜游|夜间|夜晚|晚上|夜里', query)


def parse_minutes(text):
    text = (text or '').strip().lower().replace('个', '')
    if text in ('', '不限', '未说明'):
        return None
    if re.search(r'[-−]\s*\d|[一二两三四五六七八九十\d]+\s*天', text):
        raise ValueError('invalid single-day duration')
    if '半天' in text:
        return 240  # Explicit screening assumption, disclosed in the reply.
    numbers = dict(zip('零〇一二两三四五六七八九', (0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9)))
    def number(value):
        if value.isdigit(): return int(value)
        if '十' in value:
            left, right = value.split('十', 1)
            return numbers.get(left, 1) * 10 + numbers.get(right, 0)
        if value not in numbers: raise ValueError('unsupported Chinese duration')
        return numbers[value]
    text = re.sub(r'([零〇一二两三四五六七八九十\d]+)半小时', lambda m: str(number(m[1]) + .5)+'小时', text)
    text = re.sub(r'[零〇一二两三四五六七八九十]+(?=小时|分钟)', lambda m: str(number(m[0])), text)
    text = text.replace('半小时', '0.5小时')
    values = re.findall(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(小时|h\b|分钟|min\b)', text)
    if not values:
        raise ValueError('duration needs hours or minutes')
    if sum(unit in ('小时', 'h') for _, unit in values) > 1 or sum(unit in ('分钟', 'min') for _, unit in values) > 1:
        raise ValueError('ambiguous duration')
    minutes = sum(float(n) * (60 if unit in ('小时', 'h') else 1) for n, unit in values)
    if re.search(r'(?:小时|h)半', text):
        minutes += 30
    if not 0 < minutes <= 1440:
        raise ValueError('duration outside single-day range')
    return round(minutes, 2)


def _label(value):
    return re.sub(r'\[(?:cite|source):[^\]]*\]', '', str(value), flags=re.I).strip()[:160]


def recommend_route(query, chunks, interest=None, time_budget=None, companions=None):
    if not uses_route_catalog(query):
        return None
    candidates = []
    for chunk in chunks:
        data = chunk.get('route_data')
        if not isinstance(data, dict) or not chunk.get('chunk_id'):
            continue
        try:
            duration = parse_minutes(data.get('duration'))
        except ValueError:
            continue
        steps = data.get('route')
        if duration is not None and isinstance(steps, list) and steps and all(isinstance(s, str) for s in steps):
            candidates.append((chunk, data, duration))
    if not candidates:
        return None
    base = {'route_id': None, 'duration_minutes': None, 'budget_minutes': None,
            'duration_kind': 'knowledge_preset_estimate_not_measured', 'status': 'invalid_budget'}
    # An explicit time in this message takes precedence over the form selection.
    query_time = bool(re.search(r'小时|分钟|半天|\d+\s*(?:h\b|min\b)|[一二两三四五六七八九十\d]+\s*天', query))
    budget_text = query if query_time else time_budget
    try:
        budget = parse_minutes(budget_text)
    except ValueError:
        return base, '[emotion:think]请提供明确的分钟或小时；当前资料只支持单日路线筛选，暂不拼造多日行程。'
    base['budget_minutes'] = budget
    preferences = ' '.join(x for x in (query, interest, companions) if x)
    avoid_climb = bool(re.search(r'不登顶|不爬(?:山|楼|台阶)|避免登高|不走台阶', preferences))
    within_time = [c for c in candidates if budget is None or c[2] <= budget]
    feasible = [c for c in within_time if not (avoid_climb and any('登顶' in s for s in c[1]['route']))]
    if not feasible:
        shortest = min(candidates, key=lambda c: c[2])
        base.update(status='no_fit', minimum_minutes=shortest[2])
        if within_time:
            return base, '[emotion:think]现有预设不能同时满足您的时长和不登顶条件，不能保证存在合适路线，请向景区确认短线及无障碍条件。'
        answer = (f'[emotion:think]现有知识库方案最短约{shortest[2]:g}分钟，超过您可用的{budget:g}分钟，'
                  '不能保证在此时长内走完。建议延长时间，或咨询工作人员安排短线；本次没有生成可行路线。'
                  f" [cite:{shortest[0]['chunk_id']}]")
        return base, answer
    family = avoid_climb or bool(re.search(r'亲子|孩子|小孩|儿童|家庭|老人|长辈|轮椅|婴儿车', preferences))
    history = bool(re.search(r'历史|文化|人文|佛教|深度', preferences))
    nature = bool(re.search(r'摄影|拍照|自然|风光', preferences))
    def preference_score(candidate):
        data = candidate[1]
        text = str(data.get('name', '')) + str(data.get('target', ''))
        return (3 * int(family and bool(re.search(r'亲子|小孩|家庭', text)))
                + 2 * int(history and bool(re.search(r'历史|文化|深度', text)))
                + 2 * int(nature and bool(re.search(r'自然|风光', text))))
    selected = max(feasible, key=lambda c: (preference_score(c), -c[2]))
    chunk, data, duration = selected
    base.update(status='matched', route_id=chunk['source'], duration_minutes=duration)
    reason = '按兴趣或同行人群匹配已有方案' if preference_score(selected) else '按可用时间选择较短的已有方案，主题匹配有限'
    if budget is not None:
        reason += f'；预设约{duration:g}分钟，不超过{budget:g}分钟预算'
    if budget_text and '半天' in budget_text:
        reason += '（半天按4小时的筛选假设）'
    text = (f"[emotion:calm]【路线建议 · {_label(data.get('name', ''))}】\n"
            f"推荐理由：{reason}。\n顺序：{' → '.join(_label(s) for s in data['route'])}。\n"
            f"依据：知识库预设{_label(data['duration'])}，不是实时导航或实测步行耗时。 [cite:{chunk['chunk_id']}]\n"
            '景点开放、演出场次和步行距离需现场确认；时长仅供参考。')
    if family:
        text += '亲子或轻松路线不代表已验证无障碍通行，老人、轮椅与婴儿车的通行条件需向景区确认。'
    return base, text
