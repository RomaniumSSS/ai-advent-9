"""Структурные проверки не доказывают смысловую корректность."""


def validate(case, output):
    errors = []
    if not isinstance(output, dict):
        return ['output_type']
    expected = set(case['message_ids'])
    required = {'case_id', 'decisions', 'document_groups', 'review_groups',
                'missing_context_ids', 'notes'}
    if required - output.keys():
        errors.append('missing_fields')
    if output.get('case_id') != case['case_id']:
        errors.append('case_id')
    if not isinstance(output.get('notes'), str):
        errors.append('notes_type')
    decisions = output.get('decisions')
    if not isinstance(decisions, list):
        errors.append('decisions_type')
        decisions = []
    statuses, ids = {}, []
    for decision in decisions:
        if not isinstance(decision, dict):
            errors.append('decision_type')
            continue
        if {'message_id', 'decision', 'reason', 'flags'} - decision.keys():
            errors.append('decision_missing_fields')
        ident = decision.get('message_id')
        if type(ident) is not int:
            errors.append('message_id_type')
        else:
            ids.append(ident)
            statuses[ident] = decision.get('decision')
        if decision.get('decision') not in ('include', 'exclude', 'review'):
            errors.append('decision_status')
        if 'source_role' in decision:
            errors.append('source_role_override')
        if not isinstance(decision.get('reason'), str) or not decision['reason'].strip():
            errors.append('missing_reason')
        flags = decision.get('flags')
        if not isinstance(flags, list) or any(not isinstance(f, str) or f not in
                ('needs_fact_check', 'mixed_content', 'incomplete_context') for f in flags):
            errors.append('invalid_flags')
    if len(ids) != len(set(ids)) or set(ids) != expected:
        errors.append('decision_coverage')
    missing = output.get('missing_context_ids')
    if not isinstance(missing, list) or any(type(i) is not int or i in expected for i in missing):
        errors.append('missing_context_ids')
        missing = []
    for field, status in [('document_groups', 'include'), ('review_groups', 'review')]:
        groups = output.get(field)
        if not isinstance(groups, list):
            errors.append(field + '_type')
            groups = []
        members = []
        for group in groups:
            if not isinstance(group, dict):
                errors.append(field + '_group_type')
                continue
            if {'message_ids', 'context_ids', 'reason'} - group.keys():
                errors.append(field + '_missing_fields')
            if not isinstance(group.get('reason'), str) or not group['reason'].strip():
                errors.append(field + '_reason')
            group_ids = group.get('message_ids')
            if not isinstance(group_ids, list) or any(type(i) is not int for i in group_ids):
                errors.append(field + '_membership')
                group_ids = []
            members.extend(group_ids)
            if not group_ids or any(statuses.get(i) != status for i in group_ids):
                errors.append(field + '_membership')
            context = group.get('context_ids')
            if not isinstance(context, list) or any(type(i) is not int for i in context):
                errors.append(field + '_context')
            elif set(context) - expected - set(missing):
                errors.append(field + '_context')
        wanted = {i for i, s in statuses.items() if s == status}
        if set(members) != wanted or len(members) != len(set(members)):
            errors.append(field + '_coverage')
    return sorted(set(errors))


def input_context_errors(case, messages):
    if not isinstance(messages, list):
        return ['context_input_container']
    if any(not isinstance(m, dict) or type(m.get('id')) is not int for m in messages):
        return ['context_input_message_type']
    ids = [m['id'] for m in messages]
    if len(ids) != len(set(ids)):
        return ['context_input_duplicate_id']
    if not set(case['message_ids']) <= set(ids):
        return ['context_input_missing_case_id']
    for m in messages:
        if m.get('reply_to') is not None and type(m['reply_to']) is not int:
            return ['context_input_reply_type']
        if 'attachment_presence' in m and m['attachment_presence'] is not None and type(m['attachment_presence']) is not bool:
            return ['context_input_attachment_type']
        if 'content_read' in m and type(m['content_read']) is not bool:
            return ['context_input_read_type']
    return []


def diagnose_context(case, messages, output):
    """Отдельный guard: связь include-ответа с непрочитанным медиа-родителем."""
    input_errors = input_context_errors(case, messages)
    if input_errors:
        return input_errors
    if validate(case, output):
        return ['context_diagnostic_requires_valid_output']
    inputs = {m['id']: m for m in messages if isinstance(m, dict) and type(m.get('id')) is int}
    allowed = set(case['message_ids'])
    issues = []
    for decision in output['decisions']:
        if decision['decision'] != 'include':
            continue
        ident = decision['message_id']
        parent_id = inputs.get(ident, {}).get('reply_to')
        if type(parent_id) is not int or parent_id not in allowed:
            continue
        parent = inputs.get(parent_id, {})
        if parent.get('attachment_presence') is not True or parent.get('content_read') is not False:
            continue
        if 'incomplete_context' not in decision['flags']:
            issues.append(f'{ident}:unread_parent_missing_flag')
        group = next(g for g in output['document_groups'] if ident in g['message_ids'])
        if parent_id not in group['context_ids']:
            issues.append(f'{ident}:unread_parent_missing_context')
    return issues
