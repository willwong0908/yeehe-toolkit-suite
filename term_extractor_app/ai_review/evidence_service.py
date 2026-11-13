"""Bounded, read-only evidence requests over the current task's frozen inputs."""
from __future__ import annotations

import hashlib
import json
import asyncio
from typing import Any

PROTOCOL_VERSION = 2
EVIDENCE_INSTRUCTION = """按需查证工作方法（不改变本次审校范围）：
完整检查每条原译文和独立问题，不能因规范或案例相似而整条免检。
若存在会影响判断的具体疑点，可在最终 JSON 顶层额外返回 context_requests 数组；明确的条目无需请求。
如果拟报错的依据是对文本用途、项目命名惯例或占位符展开的推测，且现有信息不足以证实，必须先提交查证请求，不能把推测当成已确认错误。例如是否应翻译某个名称取决于界面用途时，应搜索同用途条目的实际写法，而不是直接判未翻译。
专有建筑、道具、角色名称与字面译法不一致时，先区分项目命名与可由句内证实的指代错误。仅凭回译不同不得判术语错误。缺少项目命名依据且影响结论时，必须返回对应的 context_requests 并写明需要核对哪两个名称。
每项为 {"item_id":"本批ID","kind":"search|neighbors|terms|rules","query":"具体关键词或规范ID","field":"all|source|target|info","reason":"要解决的具体疑点"}。
判断依赖项目正式译名时，必须包含 kind=terms、requires_project_term=true 的请求，query 逐字填写原文中的待核对术语。普通句意查证不设置此标记。
search 仅查同文件的原译文及真实参考信息；neighbors 只查同文件同工作表邻行，位置相邻不代表相关；terms 查冻结术语；rules 查本次会话规范。
可为已报问题核实依据，也可为尚未报错但有具体风险的条目查证；不得把不确定直接当作无错。每批最多3个条目、每个条目最多2项请求。
items 仍须完整返回全部本批ID，包含当前判断。不要为了调用工具而查资料，不编造角色、技能ID、标签展开或项目规定。
会话规范仅解决其适用范围内的具体疑点；允许意译不等于可以改变条件、数值、否定或作用对象。术语推荐不等于每处都强制替换。
{name=value} 可能是合法的词形或默认值语法，变量数量差异也可能是并列修饰；未查到引擎定义时不能断言标签失效。
""".strip()

VERIFICATION_INSTRUCTION = """这是按需查证复核。只复核本次指定ID，保持原审校范围，逐项检查原判断及其他独立问题。
资料和原判断均可能不充分，不能把已有译文的重复出现当作正确答案。未查到依据时明确保留疑点，不编造规范。
仅在取得具体证据且该证据确实解决原报错时才能撤回问题。新增或撤回问题时，返回 evidence_refs（使用本次返回的证据引用）及 verification_reason（简短中文说明证据如何解决疑点）；还存在任何独立错误时不得整条改为无错。
每条必须给 verification_reason。优先回到原译文判断：若依据来自当前句，逐字摘录 source_quote 和 target_quote，说明这两处如何解决疑点，可替代外部引用。原译文支持现有译法、没有具体剩余风险时判无错。
只有缺少会改变结论的项目事实才填写 project_question（问项目方一个具体问题，指出所涉词句）及 decision_impact（不同答案分别如何影响当前译法）。此时 has_issue 只记录已经确定的独立错误；若有，必须另填 independent_issue，说明与该问题无关且不受答案影响的具体错误。若唯一争议是官方名称，即使字面不同，也只提问，不建议替换。不能用“请核实译文”等泛泛提问。
保持完整修改建议，不能遗漏未修改的段落、Tag或变量。最后只返回 items JSON，不再发起查证请求。
逐项回答 questions 中的具体疑点。verification_reason 写清“哪条资料或哪处原译文→能证明什么”。对于 required_terms，只有该原文术语本身的项目术语记录可用于确定正式译名；应引用对应记录并写明登记译名。查不到时必须给 project_question 和 decision_impact，点名原文、当前译名和需要项目方提供的信息。查到当前句或多个重复译法不能证明正式译名。
""".strip()


def verification_display(audit: dict, has_issue: bool) -> tuple[str, str]:
    if not audit.get('unresolved'):
        if audit.get('basis'):
            return ('是' if has_issue else '否'), '初审疑点：' + '；'.join(dict.fromkeys(audit['questions'])) + '\n复核依据：' + audit['basis'] + '\n判断：' + audit['reason']
        return '', ''
    if audit.get('status') == 'project':
        label = '需项目确认'
        detail = audit['question'] + ' ' + audit['impact']
        if audit.get('evidence_gap'):
            detail = audit['evidence_gap'] + '\n' + detail
    else:
        label = '复核未完成'
        detail = audit.get('failure') or '历史结果缺少完整查证记录。'
        if audit.get('questions'):
            detail += ' 初审疑点：' + '；'.join(audit['questions'])
        detail += ' 初审' + ('发现问题' if has_issue else '未发现问题') + '，可重新审校此条。'
        return label, detail
    return ('是（另需项目确认）' if has_issue else label), detail


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode('utf8')).hexdigest()


def _info(item: dict) -> list:
    value = item.get('info') or item.get('info_json') or []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = []
    value = list(value) if isinstance(value, list) else []
    location=item.get('location') or item.get('location_json') or {}
    if isinstance(location,str):
        try:location=json.loads(location)
        except ValueError:location={}
    if isinstance(location,dict):
        for entry in location.get('evidence_info',[]):
            if isinstance(entry,dict) and entry not in value:value.append(entry)
    return value


def _document_key(item: dict) -> tuple:
    location=item.get('location') or item.get('location_json') or {}
    if isinstance(location,str):
        try:location=json.loads(location)
        except ValueError:location={}
    return (str(item.get('source_file') or ''), str(location.get('attachment_id') or '') if isinstance(location,dict) else '')


def attach_evidence_context(plan: dict, documents: dict) -> None:
    """Keep real auxiliary cells available even when a saved mapping omitted them."""
    allowed={'key','id','namespace','comment','context','speaker','character','scene','oldversion',
             '备注','上下文','说话人','角色','场景','旧版本','注释'}
    rows={}
    for attachment_id,document in documents.items():
        for block in document.blocks:
            metadata=block.metadata or {}
            label=str(metadata.get('header') or block.label or '').strip()
            if label.casefold().replace(' ','').replace('_','') not in allowed:
                continue
            scope=str(metadata.get('sheet') or ('table' if document.file_type in {'csv','tsv'} else ''))
            key=(attachment_id,scope,metadata.get('row'))
            rows.setdefault(key,[]).append({'category':label,'value':block.text})
    for target in plan.get('targets',[]):
        for unit in target.get('units',[]):
            metadata=unit.setdefault('metadata',{})
            key=(metadata.get('attachment_id'),str(metadata.get('scope') or ''),metadata.get('row'))
            if key in rows:
                metadata['evidence_info']=rows[key]


def _record(item: dict) -> dict:
    # No stored path or cross-session data is exposed.
    return {'source':str(item.get('source_text') or ''), 'target':str(item.get('target_text') or ''),
            'info':_info(item), 'file':str(item.get('source_file') or ''),
            'sheet':str(item.get('sheet_name') or ''), 'position':str(item.get('segment_id') or item.get('row_number') or item.get('item_order') or '')}


class EvidenceIndex:
    def __init__(self, items: list[dict], config: dict):
        self.items = items
        self.by_id = {str(item['id']):item for item in items}
        self.config = config
        self.terms = list(config.get('memoq_term_pairs') or [])
        for item in items:
            self.terms.extend(item.get('term_pairs') or [])

    def lookup(self, owner: dict, selector: dict) -> tuple[dict, dict]:
        kind = str(selector.get('kind') or '')
        query = str(selector.get('query') or '').strip()[:160]
        field = selector.get('field', 'all')
        if kind not in {'search','neighbors','terms','rules'} or field not in {'all','source','target','info'}:
            raise ValueError('无效的查证请求')
        if kind != 'neighbors' and not query:
            raise ValueError('查证关键词不能为空')
        same_file = [item for item in self.items if _document_key(item) == _document_key(owner)]
        if kind == 'neighbors':
            same_sheet = [item for item in same_file if item.get('sheet_name') == owner.get('sheet_name')]
            position = next((i for i,item in enumerate(same_sheet) if item['id']==owner['id']), -1)
            matches = same_sheet[max(0,position-2):position]+same_sheet[position+1:position+3] if position >= 0 else []
        elif kind == 'search':
            needle = query.casefold()
            keys = ['source','target','info'] if field=='all' else [field]
            matches = [item for item in same_file if any(needle in (str(_record(item)[key]) if key!='info' else _json(_info(item))).casefold() for key in keys)]
        elif kind == 'terms':
            needle=query.casefold()
            matches=[term for term in self.terms if needle in _json(term).casefold() or str(term.get('source') or '').casefold() in needle]
            matches=list({_json(term):term for term in matches}.values())
        else:
            needle=query.casefold()
            matches=[rule for rule in self.config.get('memory_snapshot',{}).get('rules',[]) if rule.get('active') and (needle in _json(rule).casefold())]
        canonical = [_record(item) for item in matches] if kind in {'neighbors','search'} else matches
        dependency = {'selector':{'kind':kind,'query':query,'field':field}, 'digest':_digest(canonical)}
        # Hash ALL matches (including omitted matches); membership changes invalidate cache.
        records = []
        chars = 0
        for index, record in enumerate(canonical[:8],1):
            ref='ev_'+_digest({'selector':dependency['selector'],'record':record})[:16]
            value={'ref':ref, **record}
            size=len(_json(value))
            if chars+size>10000:
                break
            chars+=size
            records.append(value)
        result={'kind':kind,'query':query,'total':len(canonical),'records':records,
                'note':'仅为同文件资料，关联和正确性仍需核实；未提供运行时标签定义。'}
        return result, dependency

    def cache_valid(self, item: dict, cached: dict) -> bool:
        audit=cached.get('_verification')
        if not audit:
            return True
        if audit.get('unresolved'):
            return False
        for dependency in audit.get('dependencies',[]):
            try:
                _, current=self.lookup(item,dependency['selector'])
                if current['digest']!=dependency['digest']:
                    return False
            except (KeyError,ValueError,TypeError):
                return False
        return True


def collect_requests(parsed: dict, package: list[dict]) -> dict[str,list[dict]]:
    allowed={str(item['id']) for item in package}
    requests=parsed.get('context_requests') or []
    if not isinstance(requests,list):
        return {}
    grouped: dict[str,list[dict]]={}
    for request in requests[:12]:
        if not isinstance(request,dict):
            continue
        id_=str(request.get('item_id') or '')
        if id_ not in allowed or not str(request.get('reason') or '').strip():
            continue
        if id_ not in grouped and len(grouped)>=3:
            continue
        group=grouped.setdefault(id_,[])
        if len(group)<2:
            group.append({'item_id':id_,'kind':str(request.get('kind') or ''),'field':str(request.get('field') or 'all'),
                          'query':str(request.get('query') or '')[:160],'reason':str(request['reason'])[:800],
                          'requires_project_term':request.get('requires_project_term') is True})
    return grouped


def suggestion_problem(item: dict, result: dict) -> str:
    """Reject concrete losses, without inventing a general placeholder grammar."""
    import re
    from collections import Counter
    if not result.get('has_issue'):
        return ''
    suggestion=str(result.get('suggestion') or '')
    target=str(item.get('target_text') or '')
    if not suggestion.strip():
        return '修改建议为空'
    original_tokens=Counter(re.findall(r'\{[^{}\r\n]+\}|</?[^<>\r\n]+>|\[/?(?:color|size|b|i|u|s)(?:=[^\]]*)?\]',target))
    new_tokens=Counter(re.findall(r'\{[^{}\r\n]+\}|</?[^<>\r\n]+>|\[/?(?:color|size|b|i|u|s)(?:=[^\]]*)?\]',suggestion))
    source_tokens=Counter(re.findall(r'\{[^{}\r\n]+\}|</?[^<>\r\n]+>|\[/?(?:color|size|b|i|u|s)(?:=[^\]]*)?\]',str(item.get('source_text') or '')))
    # Preserve tokens already shared by source+target. Repairs to differing tokens are allowed.
    if (original_tokens & source_tokens)-new_tokens:
        return '修改建议遗漏原译文共有的变量或Tag'
    if len(target)>180 and len(suggestion)<len(target)*0.7:
        return '修改建议明显短于整条译文，可能遗漏段落'
    return ''


async def verify_response(request, response, *, index: EvidenceIndex, send, config: dict, parse, validate, log=lambda message:None, timeout_seconds: float = 90):
    """Give each verification call its own provider timeout, including the one allowed retry."""
    from ..models import LLMRequest
    if not response.success:
        return response
    package=list(request.metadata.get('package') or [])
    parsed=parse(response.content)
    validate(parsed,package,config)
    requests=collect_requests(parsed,package)
    if not requests:
        return response
    original={str(item['id']):dict(item) for item in parsed['items']}
    selected=[item for item in package if item['id'] in requests]
    evidence, dependencies, term_refs={},{},{}
    for item in selected:
        id_=item['id'];evidence[id_]=[];dependencies[id_]=[];term_refs[id_]={}
        for selector in requests[id_]:
            needs_term = selector['requires_project_term'] or (selector['kind']=='terms' and
                any(word in selector['reason'] for word in ('项目既定译名','官方译名','官方名称','项目定名')))
            if needs_term:
                selector = {**selector,'kind':'terms'}
            try:
                records,dependency=index.lookup(item,selector)
                evidence[id_].append(records);dependencies[id_].append(dependency)
                if needs_term:
                    query = selector['query'].strip().casefold()
                    term_refs[id_][selector['query']] = [r['ref'] for r in records['records']
                        if str(r.get('source') or '').strip().casefold()==query and r.get('target')]
            except ValueError:
                evidence[id_].append({'error':'无效请求或没有可查询的资料'})
    user={'items':[{'id':item['id'],**_record(item)} for item in selected],
          'initial_results':[original[item['id']] for item in selected],
          'questions':requests,'evidence':evidence,'required_terms':term_refs}
    followup=LLMRequest(task_id=request.task_id+'_evidence',task_type=request.task_type,
        prompt=_json(user),messages=[{'role':'system','content':request.messages[0]['content']+'\n\n'+VERIFICATION_INSTRUCTION},
                                  {'role':'user','content':_json(user)}],
        metadata={key:value for key,value in request.metadata.items() if key not in {'stream_phase_callback','package'}})
    log(f'按需查证 {len(selected)} 条，每次复核限时 {timeout_seconds:g} 秒，最多重试一次。')
    remaining_ids = {item['id'] for item in selected}
    failure = '复核超时。'
    for attempt in range(2):
        started = asyncio.get_running_loop().time()
        try:
            checked = await asyncio.wait_for(send(followup), timeout=timeout_seconds)
            if not checked.success:
                failure = '复核超时。' if checked.error_type == 'timeout' else '模型复核请求失败。'
                continue
            updated = parse(checked.content)
            validate(updated, selected, config)
            by_id = {str(row['id']): row for row in updated['items']}
            failure = '复核结果缺少有效说明或引用。'
            for item in selected:
                id_ = item['id']
                if id_ not in remaining_ids:
                    continue
                after = by_id[id_]
                refs = {r['ref'] for block in evidence[id_] for r in block.get('records', [])}
                used = after.get('evidence_refs') or []
                reason = str(after.get('verification_reason') or '').strip()
                src = str(after.get('source_quote') or '').strip()
                tgt = str(after.get('target_quote') or '').strip()
                quoted = bool(src and tgt and src in item['source_text'] and tgt in item['target_text'])
                question = str(after.get('project_question') or '').strip()
                impact = str(after.get('decision_impact') or '').strip()
                missing_terms = [term for term, matches in term_refs[id_].items() if not matches]
                if missing_terms and not question:
                    question = '请项目方确认：' + '；'.join(dict.fromkeys(
                        q['reason'] for q in requests[id_] if q['query'] in missing_terms))
                    impact = '若当前译名为项目指定用语则保留，否则按项目提供的正式译名修改。'
                if not isinstance(used, list) or any(not isinstance(ref,str) or ref not in refs for ref in used):
                    continue
                if not question and any(not any(ref in used for ref in matches)
                                        for matches in term_refs[id_].values()):
                    continue
                if question and after.get('has_issue') and not str(after.get('independent_issue') or '').strip():
                    if config.get('mode') == 'directional':
                        continue
                    after = {**after, 'has_issue':False, 'issue':'', 'issue_type':'', 'suggestion':''}
                if bool(question) != bool(impact) or not reason or suggestion_problem(item, after):
                    continue
                changed = bool(original[id_].get('has_issue')) != bool(after.get('has_issue'))
                if not (used or quoted) and (not question or (changed and after.get('has_issue'))):
                    continue
                basis = []
                if quoted:
                    basis.append(f'当前原文「{src}」与译文「{tgt}」')
                for block in evidence[id_]:
                    for record in block.get('records', []):
                        if record['ref'] in used:
                            if block['kind'] == 'rules':
                                basis.append('会话规范：' + str(record.get('text') or record.get('id')))
                            else:
                                location = '项目术语' if block['kind']=='terms' else f"{record.get('sheet','')} 第{record.get('position','')}行"
                                basis.append(f"{location}：{record.get('source','')} → {record.get('target','')}")
                after['_verification'] = {'dependencies': dependencies[id_], 'unresolved': bool(question),
                    'basis':'；'.join(basis),'evidence_gap': ('本次术语资料未找到对应译名：' + '、'.join(missing_terms)) if missing_terms else '',
                    'status': 'project' if question else 'resolved', 'question': question, 'impact': impact,
                    'source_quote': src, 'target_quote': tgt,
                    'questions': [q['reason'] for q in requests[id_]], 'reason': reason, 'evidence_refs': used}
                original[id_] = after
                remaining_ids.remove(id_)
            if not remaining_ids:
                break
        except asyncio.TimeoutError:
            failure = '复核超时。'
        except Exception as exc:
            failure = '复核请求或返回格式异常。'
            log('查证未完成：' + type(exc).__name__)
        finally:
            elapsed = asyncio.get_running_loop().time() - started
            log(f'复核第 {attempt+1} 次耗时 {elapsed:.1f} 秒，' + (failure if remaining_ids else '已完成。'))
        if attempt == 0:
            followup.messages[-1]['content'] += '\n请按复核协议补全具体结论及对应证据，逐字引用原译文或使用有效的 evidence_refs。'
    for id_ in remaining_ids:
        original[id_]['_verification'] = {'dependencies': dependencies[id_], 'unresolved': True,
            'status': 'failed', 'failure': failure, 'questions': [q['reason'] for q in requests[id_]]}
    response.content=_json({'items':[original[str(item['id'])] for item in parsed['items']]})
    return response
