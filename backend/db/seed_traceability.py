"""全链路溯源演示数据：首次启动且 trace_batch 为空时自动写入。

数据覆盖“孵化 → 育雏 → 生长 → 防疫 → 出栏 → 屠宰 → 质检 → 冷链 → 销售”九个环节，
其中既有在养批次，也有走到冷链/销售环节的批次，便于前端直接演示完整链路。
"""
import json
from datetime import datetime, timedelta

from sqlalchemy import func, select

from db.models import FarmDailyRecord, TraceBatch, TraceEvent
from db.session import SessionLocal


def _dt(month: int, day: int, hour: int = 8, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute)


def _ev(stage, title, when, location, operator, detail=None, evidence=None) -> TraceEvent:
    return TraceEvent(
        stage=stage,
        title=title,
        event_time=when,
        location=location,
        operator=operator,
        detail=json.dumps(detail or {}, ensure_ascii=False),
        evidence=json.dumps(evidence or [], ensure_ascii=False),
        status="done",
    )


def _attach(batch: TraceBatch, events: list[TraceEvent]) -> None:
    for index, event in enumerate(events, start=1):
        event.sequence = index
        batch.events.append(event)


def _build_batches() -> list[TraceBatch]:
    # 批次1：在养，当前处于防疫观察阶段，带一条中风险巡栏记录
    a01 = TraceBatch(
        batch_no="GE-2026-0815-A01",
        farm_name="澄海隆都生态鹅场",
        breed="狮头鹅",
        house_no="1号棚",
        hatch_date=_dt(8, 15, 8, 30),
        entry_date=_dt(8, 16, 9, 0),
        quantity=1200,
        current_quantity=1168,
        status="growing",
        current_stage="health",
        risk_level="medium",
    )
    _attach(a01, [
        _ev("incubation", "种蛋入孵与雏鹅检疫", _dt(8, 15, 8, 30), "澄海种鹅场孵化车间", "林伟",
            {"种蛋来源": "澄海种鹅场核心群", "入孵数量": "1,300 枚", "受精率": "94.6%", "出雏数量": "1,218 羽"},
            ["种蛋检疫证明 GD-ZD-2026-0815", "孵化记录 HATCH-0815-A01"]),
        _ev("brooding", "育雏期温湿度与开口管理", _dt(9, 1, 9, 0), "1号育雏舍", "陈晓",
            {"日龄": "1-14 日龄", "保温曲线": "32℃ → 28℃", "成活率": "98.2%", "免疫": "小鹅瘟首免"},
            ["育雏温湿度记录", "免疫记录 ND-01"]),
        _ev("growing", "转入生长舍与分群", _dt(9, 20, 10, 0), "1号生长舍", "陈晓",
            {"饲养密度": "4.5 羽/㎡", "日粮蛋白": "17.5%", "平均体重": "1.85 kg"},
            ["转群记录 GROW-0920-A01"]),
        _ev("health", "小鹅瘟/禽流感加强免疫", _dt(10, 5, 14, 20), "场区兽医室", "王医生",
            {"抽检数量": "30 羽", "抗体合格率": "96.7%", "疫苗批号": "ND-2026-0928"},
            ["免疫证明 IMM-2026-1005", "抗体检测报告"]),
        _ev("health", "巡栏发现异常与隔离处置", _dt(11, 10, 16, 40), "1号棚", "王医生",
            {"异常数量": "6 羽", "主要表现": "精神沉郁、采食下降", "环境湿度": "78%", "处置": "隔离观察 + 加强通风"},
            ["巡栏记录 2026-11-10", "隔离处置单"]),
    ])

    # 批次2：在养，链路只走到防疫，用于展示“待补齐”的中间态
    b02 = TraceBatch(
        batch_no="GE-2026-0920-B02",
        farm_name="饶平柘林湾鹅场",
        breed="马岗鹅",
        house_no="3号棚",
        hatch_date=_dt(9, 20, 7, 40),
        entry_date=_dt(9, 21, 9, 0),
        quantity=800,
        current_quantity=792,
        status="growing",
        current_stage="health",
        risk_level="low",
    )
    _attach(b02, [
        _ev("incubation", "鹅苗出雏与产地检疫", _dt(9, 20, 7, 40), "饶平孵化中心", "周海",
            {"入孵数量": "860 枚", "出雏数量": "812 羽", "弱雏": "20 羽"},
            ["产地检疫证明 GDRP-2026-0920", "出雏记录 HATCH-0920-B02"]),
        _ev("brooding", "育雏保温与开口水", _dt(10, 6, 8, 30), "3号育雏舍", "李敏",
            {"保温": "31℃ → 27℃", "开口水": "葡萄糖 + 电解多维", "成活率": "99.0%"},
            ["育雏记录 BR-1006-B02"]),
        _ev("growing", "转群与生长评估", _dt(11, 2, 10, 0), "3号生长舍", "李敏",
            {"饲养密度": "4.2 羽/㎡", "平均体重": "2.35 kg", "均匀度": "91%"},
            ["转群记录 GROW-1102-B02"]),
        _ev("health", "禽流感加强免疫", _dt(11, 18, 15, 0), "场区兽医室", "黄医生",
            {"免疫数量": "792 羽", "疫苗批号": "AI-2026-1105", "应激观察": "正常"},
            ["免疫记录 IMM-2026-1118"]),
    ])

    # 批次3：完整走完孵化到销售，作为“全链路可追溯”的展示样例
    c03 = TraceBatch(
        batch_no="GE-2026-0610-C03",
        farm_name="兴宁合水生态养殖基地",
        breed="皖西白鹅",
        house_no="5号棚",
        hatch_date=_dt(6, 10, 8, 10),
        entry_date=_dt(6, 11, 9, 0),
        quantity=600,
        current_quantity=0,
        status="sold",
        current_stage="sales",
        risk_level="low",
    )
    _attach(c03, [
        _ev("incubation", "种蛋入孵与出雏", _dt(6, 10, 8, 10), "兴宁孵化车间", "罗强",
            {"入孵数量": "650 枚", "受精率": "95.2%", "出雏数量": "612 羽"},
            ["种蛋检疫证明 GDXN-2026-0610", "孵化记录 HATCH-0610-C03"]),
        _ev("brooding", "育雏期饲养与首免", _dt(6, 26, 9, 0), "5号育雏舍", "罗强",
            {"日龄": "1-16 日龄", "成活率": "98.7%", "首免": "小鹅瘟"},
            ["育雏记录 BR-0626-C03", "首免记录"]),
        _ev("growing", "生长育成与分群", _dt(7, 18, 10, 30), "5号生长舍", "何丽",
            {"饲养密度": "4.0 羽/㎡", "日粮蛋白": "17.0%", "平均体重": "2.8 kg"},
            ["转群记录 GROW-0718-C03"]),
        _ev("health", "免疫与抗体抽检", _dt(8, 22, 14, 0), "场区兽医室", "何丽",
            {"抽检数量": "25 羽", "抗体合格率": "97.5%", "健康状态": "良好"},
            ["抗体检测报告 AB-0822-C03"]),
        _ev("outbound", "出栏申报与检疫合格", _dt(9, 28, 9, 30), "兴宁合水养殖基地", "张检疫员",
            {"出栏数量": "600 羽", "检疫结论": "合格", "运输车辆": "粤M·D3821"},
            ["动物检疫合格证明 GDSY-2026-10231", "车辆消毒记录"]),
        _ev("slaughter", "屠宰加工与宰后检验", _dt(10, 2, 8, 30), "梅州家禽屠宰加工厂", "刘师傅",
            {"屠宰批次": "SL-2026-1002-05", "宰前检验": "合格", "宰后检验": "合格", "加工方式": "冰鲜分割"},
            ["屠宰记录 SL-2026-1002-05", "宰后检验单"]),
        _ev("quality", "产品质检与分级", _dt(10, 2, 15, 20), "加工厂质检室", "陈质检员",
            {"兽药残留": "未检出", "菌落总数": "符合标准", "分级": "一级", "出品率": "72.5%"},
            ["质检报告 QC-2026-1002-05", "产品合格证"]),
        _ev("coldchain", "冷库入库与冷链发运", _dt(10, 3, 9, 10), "梅州冷链中心", "温控员小吴",
            {"冷库温度": "-18℃", "运输温度": "-16℃ ~ -18℃", "发运数量": "436 kg", "目的地": "广州天河"},
            ["冷库入库单 CC-1003-01", "冷链温度记录"]),
        _ev("sales", "终端门店签收与销售", _dt(10, 5, 11, 0), "广州天河兴安市场 A12 档", "店主黄姐",
            {"签收数量": "436 kg", "销售渠道": "社区生鲜门店", "追溯码展示": "已张贴", "售罄日期": "2026-10-07"},
            ["门店签收单 SALE-1005-A12", "追溯码照片"]),
    ])

    # 批次4：正在加工/冷链环节，出栏之后、销售之前
    d04 = TraceBatch(
        batch_no="GE-2026-0705-D04",
        farm_name="梅州丙村智慧鹅场",
        breed="狮头鹅",
        house_no="2号棚",
        hatch_date=_dt(7, 5, 8, 0),
        entry_date=_dt(7, 6, 9, 0),
        quantity=500,
        current_quantity=0,
        status="processing",
        current_stage="coldchain",
        risk_level="low",
    )
    _attach(d04, [
        _ev("incubation", "鹅苗孵化与检疫", _dt(7, 5, 8, 0), "丙村孵化中心", "邓师傅",
            {"入孵数量": "540 枚", "出雏数量": "508 羽", "检疫": "合格"},
            ["孵化记录 HATCH-0705-D04", "产地检疫证明"]),
        _ev("brooding", "育雏与开口管理", _dt(7, 22, 9, 0), "2号育雏舍", "邓师傅",
            {"成活率": "98.8%", "保温": "32℃ → 28℃"}, ["育雏记录 BR-0722-D04"]),
        _ev("growing", "生长育成与称重", _dt(8, 15, 10, 0), "2号生长舍", "叶师傅",
            {"平均体重": "3.1 kg", "均匀度": "90%", "密度": "3.8 羽/㎡"}, ["生长记录 GROW-0815-D04"]),
        _ev("health", "免疫与健康巡栏", _dt(9, 10, 14, 0), "场区兽医室", "叶师傅",
            {"免疫": "禽流感加强免疫", "抽检": "20 羽", "结论": "健康"},
            ["免疫记录 IMM-0910-D04"]),
        _ev("outbound", "出栏检疫与装车", _dt(10, 12, 8, 0), "丙村智慧鹅场", "张检疫员",
            {"出栏数量": "500 羽", "检疫": "合格", "车辆": "粤M·F7719"},
            ["检疫合格证明 GDXJ-2026-1012", "车辆消毒记录"]),
        _ev("slaughter", "屠宰加工", _dt(10, 15, 8, 30), "梅州家禽屠宰加工厂", "刘师傅",
            {"屠宰批次": "SL-2026-1015-02", "宰前检验": "合格", "宰后检验": "合格"},
            ["屠宰记录 SL-2026-1015-02"]),
        _ev("quality", "质检与分级", _dt(10, 15, 15, 0), "加工厂质检室", "陈质检员",
            {"兽药残留": "未检出", "分级": "一级", "出品率": "71.8%"},
            ["质检报告 QC-2026-1015-02"]),
        _ev("coldchain", "冷库入库待发运", _dt(10, 16, 9, 0), "梅州冷链中心", "温控员小吴",
            {"冷库温度": "-18℃", "入库数量": "358 kg", "待发运": "广州/深圳"},
            ["冷库入库单 CC-1016-02"]),
    ])

    return [a01, b02, c03, d04]


def _record(batch, days_ago, mortality, culling, feed_kg, water_l, temperature, humidity,
            symptoms="", action="", note="", created_by="场长"):
    """按“几天前”生成一条日常巡栏记录，保证演示数据里始终有今天/最近的数据。"""
    now = datetime.now().replace(hour=7, minute=30, second=0, microsecond=0)
    record_date = now - timedelta(days=days_ago)
    return FarmDailyRecord(
        batch_id=batch.id,
        record_date=record_date,
        age_days=max(0, (record_date - batch.hatch_date).days),
        mortality=mortality,
        culling=culling,
        feed_kg=feed_kg,
        water_l=water_l,
        temperature=temperature,
        humidity=humidity,
        symptoms=symptoms,
        action=action,
        note=note,
        created_by=created_by,
    )


def _seed_daily_records(db) -> None:
    if db.scalar(select(func.count()).select_from(FarmDailyRecord)):
        return

    a01 = db.scalar(select(TraceBatch).where(TraceBatch.batch_no == "GE-2026-0815-A01"))
    if a01:
        db.add_all([
            _record(a01, 5, 0, 0, 208, 610, 27.6, 69, "", "正常巡栏", "采食饮水正常", "陈晓"),
            _record(a01, 4, 1, 0, 212, 618, 27.2, 71, "", "正常巡栏", "死淘 1 羽，已无害化处理", "陈晓"),
            _record(a01, 3, 0, 0, 210, 615, 26.8, 74, "", "正常巡栏", "通风正常", "陈晓"),
            _record(a01, 2, 2, 0, 205, 600, 27.0, 76, "2羽采食偏慢", "加强观察", "关注弱雏", "王医生"),
            _record(a01, 1, 3, 0, 198, 590, 26.5, 78, "6羽精神沉郁，采食下降", "隔离观察，加强通风", "已通知兽医复诊", "王医生"),
        ])

    b02 = db.scalar(select(TraceBatch).where(TraceBatch.batch_no == "GE-2026-0920-B02"))
    if b02:
        db.add_all([
            _record(b02, 4, 0, 0, 142, 410, 27.8, 66, "", "正常巡栏", "采食饮水正常", "李敏"),
            _record(b02, 3, 0, 0, 145, 420, 27.5, 68, "", "正常巡栏", "生长均匀", "李敏"),
            _record(b02, 2, 1, 0, 143, 415, 27.3, 67, "", "正常巡栏", "死淘 1 羽，已无害化处理", "李敏"),
            _record(b02, 0, 0, 0, 146, 422, 27.1, 65, "", "正常巡栏", "今日状态正常", "李敏"),
        ])

    db.commit()


def seed_traceability() -> None:
    """首次启动写入演示批次；daily record 表为空时补最近的巡栏记录。"""
    with SessionLocal() as db:
        if not db.scalar(select(func.count()).select_from(TraceBatch)):
            for batch in _build_batches():
                db.add(batch)
            db.commit()
        _seed_daily_records(db)
