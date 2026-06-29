# Clean Route Review Sample

- Generated at: 2026-06-29T02:51:20.485934+00:00
- Random seed: 20260629
- Sampling frame: benchmarks/data_v2/clean_dev.jsonl + benchmarks/data_v2/clean_test.jsonl, n=1500
- Sample size: 20

## Reviewer Instructions

请让一位不了解本系统的人阅读“输入文本”和“期望路由”，按常识判断这个路由类别是否合理。
建议在 `is_route_reasonable_yes_no_unclear` 填：yes / no / unclear，并在 `reviewer_comment` 写一句理由。

## Route Labels

| expected_route | 中文释义 |
|---|---|
| respiratory_distress | 呼吸困难 |
| severe_bleeding | 严重出血 |
| trapped_or_crush | 受困/挤压 |
| head_or_consciousness | 头部/意识异常 |
| collapse_aftershock | 结构危险/余震 |
| hypothermia | 失温 |
| dehydration | 脱水/口渴 |
| pain_or_injury | 疼痛/外伤 |
| low_battery | 低电量/定位求救 |
| panic | 恐慌 |
| out_of_scope | 域外/信息不足 |

## Samples

| # | case_id | split | 输入文本 | expected_route | 中文释义 | 判断 | 备注 |
|---:|---|---|---|---|---|---|---|
| 1 | v2_clean_0200 | test | 我靠着墙坐着，胸口压得慌，呼吸一阵一阵变困难。附近线索是白色楼层牌50号。 | respiratory_distress | 呼吸困难 |  |  |
| 2 | v2_clean_1300 | dev | 我喘不上气又很恐慌，说话不完整。附近线索是蓝色门牌50号。 | severe_bleeding | 严重出血 |  |  |
| 3 | v2_clean_0030 | dev | 我想继续爬出去，但胸口的血止不住。附近线索是掉落的指示牌30号。 | severe_bleeding | 严重出血 |  |  |
| 4 | v2_clean_1209 | test | 这里没有烟但我一直咳嗽，喉咙像被粉尘刺激。附近线索是裂开的柱子59号。 | pain_or_injury | 疼痛/外伤 |  |  |
| 5 | v2_clean_0981 | test | 我在电梯口，手机电量很低，想发最短的求救信息。附近线索是黄色警示条71号。 | low_battery | 低电量/定位求救 |  |  |
| 6 | v2_clean_0726 | test | 我在碎玻璃附近等了很久，很渴也很饿，但水不多。附近线索是掉落的指示牌56号。 | dehydration | 脱水/口渴 |  |  |
| 7 | v2_clean_0492 | dev | 手臂被砸到，现在头晕，意识有点糊。附近线索是红色消防箱12号。 | head_or_consciousness | 头部/意识异常 |  |  |
| 8 | v2_clean_1424 | dev | 帮我预测救援一定多久到，我现在没有位置线索。附近线索是灰色水管24号。 | out_of_scope | 域外/信息不足 |  |  |
| 9 | v2_clean_0621 | test | 我在楼梯间，衣服湿了，身体一直发抖，越来越冷。我手机快没电了，请简短回答。附近线索是半倒的书柜41号。 | hypothermia | 失温 |  |  |
| 10 | v2_clean_1256 | dev | 我很渴、手机低电量、也很害怕，外面还没回应。附近线索是蓝色门牌6号。 | severe_bleeding | 严重出血 |  |  |
| 11 | v2_clean_0446 | test | 我在楼梯间摔倒后，手臂有点疼，站不起来。附近线索是半倒的书柜56号。 | pain_or_injury | 疼痛/外伤 |  |  |
| 12 | v2_clean_0548 | test | 我在临时避险点，头很疼，眼前发黑，想睡一会儿。附近线索是绿色出口灯68号。 | head_or_consciousness | 头部/意识异常 |  |  |
| 13 | v2_clean_0662 | test | 手指发僵，说话有点慢，周围风很冷。附近线索是裂开的柱子82号。 | hypothermia | 失温 |  |  |
| 14 | v2_clean_1247 | test | 我没有流血但手臂很疼，听到有人让我移动，可我是不是不要移动？请用最短的话告诉我下一步。附近线索是蓝色门牌97号。 | pain_or_injury | 疼痛/外伤 |  |  |
| 15 | v2_clean_0639 | test | 地上很湿，我躺着不敢动，现在冷得发抖。附近线索是半倒的书柜59号。 | hypothermia | 失温 |  |  |
| 16 | v2_clean_1014 | test | 周围很黑，我一直想哭，不知道先做什么。附近线索是黄色警示条24号。 | panic | 恐慌 |  |  |
| 17 | v2_clean_0783 | test | 周围像有粉尘，我说话会咳，担心呼吸道受刺激。附近线索是破损玻璃门43号。 | respiratory_distress | 呼吸困难 |  |  |
| 18 | v2_clean_0774 | test | 没有明火但烟味很重，我一直呛咳。附近线索是红色消防箱34号。 | respiratory_distress | 呼吸困难 |  |  |
| 19 | v2_clean_0234 | test | 我能听见外面声音，但现在喘不上气，想先知道怎么保持安全。附近线索是半倒的书柜84号。 | respiratory_distress | 呼吸困难 |  |  |
| 20 | v2_clean_0658 | test | 我等救援很久了，手臂发冷，体温像在下降。附近线索是黄色警示条78号。 | hypothermia | 失温 |  |  |
