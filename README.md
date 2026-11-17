# 未披露设施的身份核查采集

本项目接收公开来源的原文及关联记录，保留各来源原文、取得时间、地块与运营主体依据，将多栋建筑、别名和同址设施区分为已核实身份与候选关系。当前样例只给出部分证据，未决状态不等于业务事实不存在。

来源响应由 transport 校验（含取得时间），domain 解释资料并解析身份关系，ledger 保留事务、版本与期次，view 展示当前证据、覆盖总体和缺口。轮廓晚到或许可更正时，身份关系与缺口随期次变化，旧期可用 `--as-of` 回查；来源不足的设施只列入缺口，不计入覆盖总体。样例为合成资料，不访问真实网站。

在项目根目录执行：

    python -m unittest discover -s tests -v
    python -m compileall -q capture_service tests
    python -m capture_service.cli inspect data/normal.json
    python -m capture_service.cli inspect data/identity.json --as-of 4
    python -m capture_service.cli epochs data/identity.json

Dockerfile 提供 Linux 环境；docker build -t facility-identity . 构建，docker run --rm facility-identity 运行样例。
