import os, re, json, random, unicodedata
import requests
import streamlit as st

st.set_page_config(page_title="普通話拼音訓練", page_icon="🗣️", layout="wide")


# ===== API 設定 =====
def get_api_config():
    base = os.environ.get("OPENAI_API_BASE", "").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY", "") or os.environ.get("SILRA_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL_NAME", "") or os.environ.get("MODEL_NAME", "deepseek-chat")
    if not base:
        silra_url = os.environ.get("SILRA_API_URL", "")
        if silra_url:
            base = silra_url.replace("/chat/completions", "").rstrip("/")
    if not base:
        base = "https://api.deepseek.com"
    return base, key, model


# ===== AI JSON 解析 =====
def parse_ai_json(content):
    if not content:
        return None
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    content = content.replace("\\\\\\\\", "\\\\")
    def _unwrap(obj):
        if isinstance(obj, dict):
            for k in ("questions", "question", "題目", "data", "quiz", "items", "results", "exercises"):
                v = obj.get(k)
                if isinstance(v, list):
                    return v
        return obj
    try:
        return _unwrap(json.loads(content))
    except json.JSONDecodeError:
        m = re.search(r'[\[{].*[\]}]', content, re.S)
        if not m:
            return None
        try:
            return _unwrap(json.loads(m.group(0)))
        except json.JSONDecodeError:
            return None


def _norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s「」『』\"'“”’（）()…·]+", "", s)


def _match_answer(ans, opts):
    if not ans:
        return None
    if ans in opts:
        return ans
    na = _norm(ans)
    if not na:
        return None
    for o in opts:
        if _norm(o) == na:
            return o
    m = re.fullmatch(r"[a-dA-D]", na)
    if m:
        idx = ord(m.group(0).upper()) - ord("A")
        if idx < len(opts):
            return opts[idx]
    m = re.match(r"^[a-dA-D][.、)）:：]\s*(.+)$", ans.strip())
    if m:
        cand = m.group(1).strip()
        for o in opts:
            if _norm(cand) == _norm(o):
                return o
        if cand in opts:
            return cand
    parts = [p.strip() for p in re.split(r"[和及或、，]", ans) if p.strip()]
    if len(parts) >= 2:
        nopts = {_norm(o): o for o in opts}
        if all(_norm(p) in nopts for p in parts):
            return None  # 一題多答案 → 唔合格
    return None


def pin(q, ans, dist, hint):
    """拼音題 helper：答案 + 3 個誘答湊夠 4 選項"""
    opts = [ans]
    for d in dist:
        if d not in opts and d != ans:
            opts.append(d)
        if len(opts) == 4:
            break
    return ("mc", q, ans, opts, hint)


# ===== 教材題庫 =====
QUESTION_BANK = {
    "ch1": {
        "name": "1️⃣ 拼音詞語・第1課《我的新居》",
        "date": "2026-10-19",
        "questions": [
            pin("「佈置」的拼音是？", "bùzhì", ["bùzì", "būzhì", "pùzhì"], "💡 「置」係翹舌音 zh，唔係平舌 z；「佈」係第四聲"),
            pin("「沙發」的拼音是？", "shāfā", ["sāfā", "shāfá", "shāfà"], "💡 「沙」係翹舌音 sh（唔係平舌 s）；兩個都係第一聲"),
            pin("「式樣」的拼音是？", "shìyàng", ["sìyàng", "shìyáng", "shìxiàng"], "💡 「式」翹舌 sh；「樣」讀 yàng（第四聲，唔係第二聲）"),
            pin("「新穎」的拼音是？", "xīnyǐng", ["xīnyǐn", "xīnyíng", "xīngyǐng"], "💡 易錯：穎係後鼻音 yǐng（唔係前鼻 yǐn）；穎係第三聲"),
            pin("「眼光」的拼音是？", "yǎnguāng", ["yǎngāng", "yǎnguǎng", "yánguāng"], "💡 「眼」第三聲 yǎn；「光」guāng（有 u 介音）"),
            pin("「房間」的拼音是？", "fángjiān", ["fángjiāng", "fǎngjiān", "fángjiǎn"], "💡 房 fáng（第二聲）；間係前鼻音 jiān（唔係後鼻 jiāng）"),
            pin("「配套」的拼音是？", "pèitào", ["bèitào", "pèitāo", "pèidào"], "💡 「配」pèi（p 送氣，唔係 b）；「套」第四聲 tào"),
        ],
    },
    "ch2": {
        "name": "2️⃣ 拼音詞語・第2課《邀約》",
        "date": "2026-10-19",
        "questions": [
            pin("「義工」的拼音是？", "yìgōng", ["yìgòng", "yǐgōng", "yìguōng"], "💡 義 yì（第四聲）；工 gōng（第一聲）"),
            pin("「延後」的拼音是？", "yánhòu", ["yánhǒu", "yínhuò", "yánghòu"], "💡 延 yán（前鼻音）；後 hòu（第四聲）"),
            pin("「刺激」的拼音是？", "cìjī", ["chìjī", "cìjí", "cìjì"], "💡 易錯：刺係平舌音 cì（唔係翹舌 chì）；激第一聲 jī"),
            pin("「恐怕」的拼音是？", "kǒngpà", ["kǒngbà", "kǒnpà", "kòngpà"], "💡 恐 kǒng（後鼻音）；怕 pà（p 送氣，唔係 b）"),
            pin("「巡遊」的拼音是？", "xúnyóu", ["xúnyǒu", "xǔnyóu", "xúnróu"], "💡 巡 xún（第二聲）；遊 yóu（第二聲）"),
        ],
    },
    "ch3": {
        "name": "3️⃣ 拼音詞語・第3課《升中面試》",
        "date": "2026-10-19",
        "questions": [
            pin("「淳樸」的拼音是？", "chúnpǔ", ["chúnpú", "cúnpǔ", "chūnpǔ"], "💡 淳 chún（翹舌）；樸 pǔ（第三聲，唔係第二聲）"),
            pin("「完善」的拼音是？", "wánshàn", ["wánshān", "wǎnshàn", "wánshǎng"], "💡 善 shàn（前鼻音 -n，第四聲，唔係後鼻 -ng）"),
            pin("「教學」的拼音是？", "jiàoxué", ["jiāoxué", "jiàoxuè", "jiàoxiě"], "💡 教 jiào（第四聲）；學 xué（第二聲）"),
            pin("「水平」的拼音是？", "shuǐpíng", ["shuǐpín", "shuǐpǐn", "suǐpíng"], "💡 易錯：平係後鼻音 píng（唔係前鼻 pín）；水第三聲"),
            pin("「類型」的拼音是？", "lèixíng", ["lèixín", "lèixǐng", "lèixìng"], "💡 型係後鼻音 xíng（唔係前鼻 xín）；類第四聲"),
            pin("「期望」的拼音是？", "qīwàng", ["qǐwàng", "qíwàng", "qīhuàng"], "💡 易錯：期讀第一聲 qī（唔係第三聲）；望 wàng"),
            pin("「結識」的拼音是？", "jiéshí", ["jiéshì", "jiéxí", "jiěshí"], "💡 易錯：識讀第二聲 shí（唔係第四聲 shì）"),
            pin("「潛能」的拼音是？", "qiánnéng", ["qiǎnnéng", "qiánnén", "qiánléng"], "💡 易錯：潛讀第二聲 qián（唔係第三聲 qiǎn）；能 néng 後鼻音"),
        ],
    },
    "ch4": {
        "name": "4️⃣ 拼音詞語・第4課《運動會》",
        "date": "2026-10-19",
        "questions": [
            pin("「賽跑」的拼音是？", "sàipǎo", ["sàibǎo", "shàipǎo", "sàipào"], "💡 賽 sài（平舌 s）；跑 pǎo（第三聲）"),
            pin("「短跑」的拼音是？", "duǎnpǎo", ["duǎnbǎo", "dǎnpǎo", "duǎnpào"], "💡 短 duǎn（有 u 介音）；跑 pǎo"),
            pin("「健將」的拼音是？", "jiànjiàng", ["jiànjiāng", "jiànjiǎng", "jiàngjiàng"], "💡 易錯：將讀第四聲 jiàng（健將＝大將），唔係第一聲 jiāng"),
            pin("「奪冠」的拼音是？", "duóguàn", ["duóguān", "duóguǎn", "duókuàn"], "💡 易錯：冠讀第四聲 guàn（奪冠），唔係第一聲 guān"),
            pin("「飛人」的拼音是？", "fēirén", ["fēiyén", "huīrén", "fēirèn"], "💡 飛 fēi（第一聲）；人 rén（第二聲）"),
            pin("「各展所長」的拼音是？", "gèzhǎnsuǒcháng", ["gèzhǎnsuǒchǎng", "gèzhǎnsuǒcáng", "gèzhǎnsuǒzhǎng"], "💡 易錯：長讀 cháng（所長＝長處），唔係 zhǎng（長大）"),
            pin("「跳高」的拼音是？", "tiàogāo", ["tiàogǎo", "tiàokāo", "diàogāo"], "💡 跳 tiào；高 gāo（第一聲）"),
            pin("「出醜」的拼音是？", "chūchǒu", ["chūchóu", "cūchǒu", "chūcǒu"], "💡 易錯：醜讀第三聲 chǒu（唔係第二聲）；出翹舌 ch"),
            pin("「打氣」的拼音是？", "dǎqì", ["dǎqī", "dǎjì", "dáqì"], "💡 打 dǎ（第三聲）；氣 qì（第四聲，q 送氣唔係 j）"),
        ],
    },
    "yicuoyin": {
        "name": "5️⃣ 易錯音辨析（平翹舌・前後鼻・多音字）",
        "date": "2026-10-19",
        "questions": [
            ("mc", "「刺激」的「刺」聲母是平舌音定翹舌音？", "平舌音 c", ["平舌音 c", "翹舌音 ch", "平舌音 z", "翹舌音 zh"], "💡 刺 cì 係平舌音 c（舌尖抵牙齒），唔係翹舌 ch"),
            ("mc", "「新穎」的「穎」係前鼻音定後鼻音？", "後鼻音 yǐng", ["後鼻音 yǐng", "前鼻音 yǐn", "後鼻音 yíng", "前鼻音 yīn"], "💡 穎讀後鼻音 yǐng（-ng），第三聲；好多學生誤讀 yǐn"),
            ("mc", "「奪冠」的「冠」讀邊個音？", "guàn（第四聲）", ["guàn（第四聲）", "guān（第一聲）", "guǎn（第三聲）", "kuàn（第四聲）"], "💡 「奪冠」＝贏冠軍，冠讀第四聲 guàn；「王冠」先讀 guān"),
            ("mc", "「各展所長」的「長」讀邊個音？", "cháng", ["cháng", "zhǎng", "cáng", "chàng"], "💡 「所長」＝擅長嘅嘢，長讀 cháng；「長大」先讀 zhǎng"),
            ("mc", "「健將」的「將」讀邊個音？", "jiàng（第四聲）", ["jiàng（第四聲）", "jiāng（第一聲）", "jiǎng（第三聲）", "zhàng（第四聲）"], "💡 「健將」＝運動健將，將讀第四聲 jiàng；「將來」先讀 jiāng"),
            ("mc", "「潛能」的「潛」讀邊個音？", "qián（第二聲）", ["qián（第二聲）", "qiǎn（第三聲）", "qiān（第一聲）", "jiàn（第四聲）"], "💡 易錯：潛讀第二聲 qián，唔係第三聲 qiǎn"),
            ("mc", "「結識」的「識」讀邊個音？", "shí（第二聲）", ["shí（第二聲）", "shì（第四聲）", "xí（第二聲）", "shǐ（第三聲）"], "💡 「結識」＝認識，識讀第二聲 shí"),
            ("mc", "「出醜」的「醜」讀邊個音？", "chǒu（第三聲）", ["chǒu（第三聲）", "chóu（第二聲）", "cǒu（第三聲）", "chòu（第四聲）"], "💡 醜讀第三聲 chǒu，翹舌音"),
            ("mc", "「眼光」的「光」韻母係？", "uang", ["uang", "ang", "uan", "ong"], "💡 光 guāng 韻母係 uang（有 u 介音），唔係 ang"),
            ("mc", "「房間」的「間」係前鼻音定後鼻音？", "前鼻音 jiān", ["前鼻音 jiān", "後鼻音 jiāng", "前鼻音 jiǎn", "後鼻音 jiàng"], "💡 間讀前鼻音 jiān（-n），第一聲，唔係後鼻 jiāng"),
        ],
    },
    "pinxie": {
        "name": "6️⃣ 拼寫規則（人名・地名・專有名詞）",
        "date": "2026-10-19",
        "questions": [
            ("mc", "人名「李白」點樣拼寫？", "Lǐ Bái（姓和名分寫）", ["Lǐ Bái（姓和名分寫）", "Lǐbái（連寫）", "Lǐ bái（全部小寫）", "LI BAI（全部大寫）"], "💡 人名：姓和名分寫，各自第一個字母大寫 → Lǐ Bái"),
            ("mc", "地名「沙田」點樣拼寫？", "Shātián（連寫）", ["Shātián（連寫）", "Shā Tián（分寫）", "shātián（全小寫）", "SHĀTIÁN（全大寫）"], "💡 地名連寫，第一個字母大寫 → Shātián"),
            ("mc", "「香港公園」點樣拼寫？", "Xiānggǎng Gōngyuán（專有＋通用分寫）", ["Xiānggǎng Gōngyuán（專有＋通用分寫）", "Xiānggǎnggōngyuán（全連寫）", "Xiāng Gǎng Gōng Yuán（全部分寫）", "xiānggǎng gōngyuán（全小寫）"], "💡 專有名詞＋通用名詞要分寫：Xiānggǎng（專有）＋Gōngyuán（通用）"),
            ("mc", "人名「杜牧」點樣拼寫？", "Dù Mù", ["Dù Mù", "Dùmù", "Dù mù", "dù mù"], "💡 姓 Dù 名 Mù 分寫，各自首字母大寫"),
            ("mc", "地名「故宮」點樣拼寫？", "Gùgōng", ["Gùgōng", "Gù Gōng", "gùgōng", "GùGōng"], "💡 地名連寫，第一個字母大寫 → Gùgōng"),
            ("mc", "國名「加拿大」點樣拼寫？", "Jiānádà", ["Jiānádà", "Jiā Ná Dà", "jiānádà", "JIĀNÁDÀ"], "💡 國名連寫，第一個字母大寫 → Jiānádà"),
            ("mc", "「上海市」點樣拼寫？", "Shànghǎi Shì（專有＋通用分寫）", ["Shànghǎi Shì（專有＋通用分寫）", "Shànghǎishì（連寫）", "Shàng Hǎi Shì（全分寫）", "shànghǎi shì（全小寫）"], "💡 「上海」專有名詞＋「市」通用名詞分寫 → Shànghǎi Shì"),
            ("mc", "複姓「司馬光」點樣拼寫？", "Sīmǎ Guāng（複姓連寫＋名分寫）", ["Sīmǎ Guāng（複姓連寫＋名分寫）", "Sī Mǎ Guāng（全分寫）", "Sīmǎguāng（全連寫）", "sīmǎ guāng（全小寫）"], "💡 複姓「司馬」連寫，名「光」分寫 → Sīmǎ Guāng"),
            ("mc", "國名「英國」點樣拼寫？", "Yīngguó", ["Yīngguó", "Yīng Guó", "yīngguó", "YīngGuó"], "💡 國名連寫，第一個字母大寫 → Yīngguó"),
            ("mc", "人名「孫中山」點樣拼寫？", "Sūn Zhōngshān（姓分寫＋名連寫）", ["Sūn Zhōngshān（姓分寫＋名連寫）", "Sūnzhōngshān（全連寫）", "Sūn Zhōng Shān（全分寫）", "sūn zhōngshān（全小寫）"], "💡 姓 Sūn 分寫，雙字名「中山」連寫 → Sūn Zhōngshān"),
        ],
    },
    "yunmu": {
        "name": "7️⃣ 韻母辨析（前後鼻・iang/uang・in/uen/un）",
        "date": "2026-10-19",
        "questions": [
            ("mc", "「產」定「場」係前鼻音？", "產 chǎn", ["產 chǎn", "場 chǎng", "兩者都係", "兩者都唔係"], "💡 產 chǎn 係前鼻音 -n；場 chǎng 係後鼻音 -ng"),
            ("mc", "「真」定「爭」係後鼻音？", "爭 zhēng", ["爭 zhēng", "真 zhēn", "兩者都係", "兩者都唔係"], "💡 爭 zhēng 後鼻音；真 zhēn 前鼻音"),
            ("mc", "「信」定「幸」係前鼻音？", "信 xìn", ["信 xìn", "幸 xìng", "兩者都係", "兩者都唔係"], "💡 信 xìn 前鼻音 -in；幸 xìng 後鼻音 -ing"),
            ("mc", "「講義」的「講」韻母係？", "iang", ["iang", "uang", "ang", "ian"], "💡 講 jiǎng 韻母係 iang；「廣義」guǎng 先係 uang"),
            ("mc", "「風霜」的「霜」韻母係？", "uang", ["uang", "iang", "ang", "uan"], "💡 霜 shuāng 韻母係 uang；「風箱」xiāng 先係 iang"),
            ("mc", "「春」chūn 的韻母係？", "un", ["un", "in", "uen", "ün"], "💡 春 chūn 韻母係 un（uen 嘅省略）"),
            ("mc", "「盡」jìn 的韻母係？", "in", ["in", "un", "ing", "en"], "💡 盡 jìn 韻母係前鼻音 in，唔係後鼻 ing"),
            ("mc", "「尋」xún 的韻母係？", "un", ["un", "in", "uen", "ün"], "💡 尋 xún 韻母係 un"),
            ("mc", "「擔心」的「擔」係前鼻音定後鼻音？", "前鼻音 dān", ["前鼻音 dān", "後鼻音 dāng", "前鼻音 dàn", "後鼻音 dàng"], "💡 擔 dān 前鼻音 -an"),
            ("mc", "「漁翁」的「翁」韻母係？", "eng（後鼻音）", ["eng（後鼻音）", "en（前鼻音）", "ong", "ang"], "💡 翁 wēng 韻母係後鼻音 eng"),
        ],
    },
}


# ===== AI 生成題庫（topic 定義）=====
AI_TOPICS = {
    "pinyin": {
        "name": "拼音詞語（看詞選拼音）",
        "context": "教材（2026-10-19 普通話拼音詞語第1至4課，共 29 詞）：第1課《我的新居》佈置、沙發、式樣、新穎、眼光、房間、配套；第2課《邀約》義工、延後、刺激、恐怕、巡遊；第3課《升中面試》淳樸、完善、教學、水平、類型、期望、結識、潛能；第4課《運動會》賽跑、短跑、健將、奪冠、飛人、各展所長、跳高、出醜、打氣。",
        "concepts": [
            "易錯音：新穎 yǐng（後鼻音）、刺 cì（平舌）、潛 qián（唔係 qiǎn）、結識 shí、期 qī、奪冠 guàn（四聲）、所長 cháng、出醜 chǒu、健將 jiàng",
            "平舌音 z/c/s vs 翹舌音 zh/ch/sh",
            "前鼻音 -n（in/en/an/ian/uen）vs 後鼻音 -ng（ing/eng/ang/iang/uang/ong）",
            "多音字：冠 guān/guàn、長 cháng/zhǎng、將 jiāng/jiàng",
        ],
    },
    "shengdiao": {
        "name": "聲調（四聲判斷）",
        "context": "普通話聲調四聲：第一聲陰平（¯）、第二聲陽平（ˊ）、第三聲上聲（ˇ）、第四聲去聲（ˋ）。香港學生易錯：潛 qián 誤讀第三聲、期 qī 誤讀第三聲、識 shí 誤讀第四聲、穎 yǐng 誤讀第二聲。",
        "concepts": [
            "第一聲：高平（期 qī、工 gōng、佈 bù 嘅對立音）",
            "第二聲：上升（潛 qián、延 yán、巡 xún、房 fáng、能 néng）",
            "第三聲：先降後升（跑 pǎo、短 duǎn、水 shuǐ、眼 yǎn、恐 kǒng）",
            "第四聲：下降（置 zhì、後 hòu、冠 guàn、將 jiàng、套 tào）",
        ],
    },
    "pinxie": {
        "name": "拼寫規則（人名・地名）",
        "context": "普通話拼寫規則（2026-10-19 語音練習）：人名姓和名分寫、各自首字母大寫（Lǐ Bái、Dù Mù）；雙字名連寫（Sūn Zhōngshān）；複姓連寫（Sīmǎ Guāng）；地名連寫（Shātián、Gùgōng）；國名連寫（Jiānádà、Yīngguó）；專有名詞＋通用名詞分寫（Xiānggǎng Gōngyuán、Shànghǎi Shì）。",
        "concepts": [
            "人名：姓＋名分寫，各自首字母大寫",
            "雙字名／複姓：內部連寫",
            "地名／國名：連寫，首字母大寫",
            "專有名詞＋通用名詞：分寫",
        ],
    },
    "yunmu": {
        "name": "韻母辨析（前後鼻・iang/uang・in/uen/un）",
        "context": "普通話韻母（2026-10-19 語音練習＋工作紙）：前後鼻韻母 6 組對比（產/場、真/爭、信/幸、燕/樣、晚/往、溫/翁）；iang vs uang（講/廣、箱/霜、槍/創）；in/uen/un（春 chūn、尋 xún、孕 yùn → un；盡 jìn → in）。",
        "concepts": [
            "前鼻音：-n（in/en/an/ian/uen/ün）",
            "後鼻音：-ng（ing/eng/ang/iang/uang/ong）",
            "iang：講、箱、槍（jiǎng、xiāng、qiāng）",
            "uang：廣、霜、創（guǎng、shuāng、chuāng）",
            "un：春 chūn、尋 xún、順 shùn、馴 xùn、訊 xùn",
            "in：盡 jìn、信 xìn",
        ],
    },
}


# ===== 頁面 =====
st.title("🗣️ 普通話拼音訓練")
st.caption("普通話拼音訓練 — 拼音詞語／聲調／易錯音／拼寫規則／韻母辨析；各 Section 獨立揀、獨立練。題目 100% 嚟自教材！")

if "pt_questions" not in st.session_state:
    st.session_state.pt_questions = []
if "pt_checked" not in st.session_state:
    st.session_state.pt_checked = False


def options_for_mode(mode_is_ai):
    if mode_is_ai:
        return [k for k in AI_TOPICS]
    return list(QUESTION_BANK.keys())


def label_for(k, mode_is_ai):
    if mode_is_ai:
        return AI_TOPICS[k]["name"]
    else:
        data = QUESTION_BANK[k]
        return f"{data['name']} ({data['date']})"


def ai_generate(count, topics):
    api_base, api_key, model = get_api_config()
    if not api_key:
        st.error("⚠️ 未偵測到 API key — 請去 app 右上 ⋯ → Settings → Secrets 設定（OPENAI_API_KEY）")
        return []
    ctx_lines, pt_lines = [], []
    for t in topics:
        info = AI_TOPICS[t]
        ctx_lines.append(f"【{info['name']}】{info['context']}")
        for c in info["concepts"]:
            pt_lines.append(f"- {c}")
    sys_prompt = f"""You are an experienced Putonghua (Mandarin) teacher in Hong Kong. Create pinyin multiple-choice questions for Primary 6 students (Kwong Ming School). All content must come ONLY from the textbook notes below — do not invent words or pinyin beyond them.

**Knowledge points (textbook only):**
{chr(10).join(pt_lines)}

**Textbook context:**
{chr(10).join(ctx_lines)}

**Question requirements:**
1. Multiple-choice questions only: 4 options each (one correct + 3 plausible distractors based on common mistakes: 平翹舌 z/c/s vs zh/ch/sh, 前後鼻 -n vs -ng, 四聲混淆, 多音字).
2. The question text, options, answer and hint must ALL be in Traditional Chinese (書面語); pinyin must use correct tone marks (āáǎà ēéěè īíǐì ōóǒò ūúǔù ǖǘǚǜ).
3. "answer" must be EXACTLY one of the options (no A/B/C/D prefix, no extra text).
4. 「hint」explains the rule (e.g. 平舌/翹舌、前鼻/後鼻、多音字、聲調).
5. SINGLE-CORRECT-ANSWER RULE: each question must have exactly ONE correct option. NEVER create multi-answer questions.
6. ANSWER-NOT-IN-QUESTION RULE: the correct answer must NOT appear inside the question text.
7. Self-check before output: is "answer" verbatim one of the 4 options? Are the other 3 options clearly wrong? Is the pinyin (including tone marks) correct? If any check fails, fix the question now.
Output ONLY a JSON array, nothing else:
[{{"question": "...", "options": ["...", "...", "...", "..."], "answer": "...", "hint": "..."}}]"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"請根據教材規則生成 {count} 條普通話拼音選擇題（4 個選項、答案必須原字照寫 options 入面嗰個選項、附 hint、拼音聲調要準確、全文繁體中文）。"},
        ],
        "max_tokens": 6000,
        "temperature": 0.5,
        "enable_thinking": False,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        r = requests.post(f"{api_base}/chat/completions", json=payload, headers=headers, timeout=180)
    except requests.exceptions.RequestException as e:
        st.error(f"❌ 連唔到 API：{e}")
        return []
    if r.status_code != 200:
        st.error(f"❌ AI 生成失敗（錯誤碼 {r.status_code}）：{r.text[:200]}")
        return []
    content = r.json()["choices"][0]["message"]["content"]
    data = parse_ai_json(content)
    if not isinstance(data, list):
        st.error("❌ AI 回覆格式唔啱，再試一次？")
        return []
    valid = []
    for item in data:
        q = (item.get("question") or "").strip()
        ans = (item.get("answer") or "").strip()
        hint = (item.get("hint") or "").strip()
        opts = item.get("options") or []
        if re.search(r"哪兩個|邊兩個|哪幾|哪些|多選|兩項|兩個答案|邊幾|which two|select all|all that apply", q):
            continue
        if not q or not ans or not isinstance(opts, list) or len(opts) != 4:
            continue
        clean_opts = [o.strip() for o in opts]
        matched = _match_answer(ans, clean_opts)
        if matched is None:
            continue
        if len(matched) >= 2 and _norm(matched) and _norm(matched) in _norm(q):
            continue
        valid.append({"q": q, "options": clean_opts, "answer": matched, "hint": hint})
    if not valid:
        st.error("❌ AI 生成嘅題目全部唔合格（答案唔喺選項入面）— 再試一次？")
    return valid[:count]


def build_round(mode_is_ai, topics, count):
    if mode_is_ai:
        with st.spinner("✨ AI 生成緊題目，請稍候…（約 10–30 秒）"):
            qs = ai_generate(count, topics)
    else:
        pool = [q for t in topics for q in QUESTION_BANK[t]["questions"]]
        random.shuffle(pool)
        qs = []
        for item in pool[:count]:
            _, q, ans, opts, hint = item
            opts = list(opts)
            random.shuffle(opts)
            qs.append({"q": q, "options": opts, "answer": ans, "hint": hint})
    if not qs:
        return False
    st.session_state.pt_questions = qs
    st.session_state.pt_checked = False
    return True


# ===== Sidebar =====
with st.sidebar:
    st.header("⚙️ 設定")
    mode_is_ai = st.radio("生成模式", ["📖 教材原題（即時・100% 教材）", "✨ AI 生成新題（qwen3.8-flash）"], key="pt_mode") == "✨ AI 生成新題（qwen3.8-flash）"
    topics = st.multiselect(
        "揀 Section（可多選，獨立訓練）",
        options_for_mode(mode_is_ai),
        format_func=lambda k: label_for(k, mode_is_ai),
        key="pt_topics",
    )
    count = st.slider("每輪題數", 5, 20, 10, key="pt_count")
    if st.button("🎲 生成題目", type="primary", use_container_width=True):
        if not topics:
            st.warning("⚠️ 請先揀至少一個 Section")
        else:
            try:
                if build_round(mode_is_ai, topics, count):
                    st.rerun()
            except Exception as e:
                st.error(f"❌ 出錯：{e}")
    if topics:
        with st.expander("📚 知識點"):
            if mode_is_ai:
                for t in topics:
                    st.markdown(f"**{AI_TOPICS[t]['name']}**（{len(AI_TOPICS[t]['concepts'])} 點）")
                    for c in AI_TOPICS[t]["concepts"]:
                        st.markdown(f"- {c}")
            else:
                for t in topics:
                    st.markdown(f"**{QUESTION_BANK[t]['name']}**（{len(QUESTION_BANK[t]['questions'])} 題）")

st.divider()

# ===== 出題 =====
if not st.session_state.pt_questions:
    st.info("👈 左邊 sidebar：揀生成模式 → 揀 Section（可多選）→ 㩒「🎲 生成題目」開始！")
    bank_total = sum(len(v["questions"]) for v in QUESTION_BANK.values())
    st.markdown(f"📚 **題庫規模：** 共 {bank_total} 條教材原題，7 個 Section：")
    for k, v in QUESTION_BANK.items():
        st.markdown(f"- **{v['name']}** — {len(v['questions'])} 題")
    st.stop()

qs = st.session_state.pt_questions
st.subheader(f"📝 今輪 {len(qs)} 題")
for i, item in enumerate(qs):
    st.radio(f"**{i + 1}.** {item['q']}", item["options"], key=f"pt_a{i}", index=None)

c1, c2 = st.columns([1, 1])
if not st.session_state.pt_checked:
    if c1.button("✅ 檢查答案", type="primary"):
        st.session_state.pt_checked = True
        st.rerun()
else:
    results = []
    for i, item in enumerate(qs):
        user = st.session_state.get(f"pt_a{i}")
        ok = (user == item["answer"]) if user else None
        results.append((i, user, ok))
    correct = sum(1 for _, _, ok in results if ok is True)
    unanswered = sum(1 for _, _, ok in results if ok is None)
    st.metric("🏆 得分", f"{correct} / {len(qs)}" + (f"（{unanswered} 題未作答）" if unanswered else ""))
    for i, user, ok in results:
        item = qs[i]
        if ok is True:
            st.success(f"**✅ 第 {i + 1} 題**（你答：{user}）")
        elif ok is None:
            st.warning(f"**⏳ 第 {i + 1} 題**　未作答　正確答案：**{item['answer']}**")
        else:
            st.error(f"**❌ 第 {i + 1} 題**　你答：{user}　正確答案：**{item['answer']}**")
        st.caption("💡 " + item["hint"])
    st.markdown("---")

if c2.button("🔄 再嚟一輪", use_container_width=True):
    mode_is_ai = st.session_state.pt_mode == "✨ AI 生成新題（qwen3.8-flash）"
    topics = st.session_state.pt_topics
    count = st.session_state.pt_count
    if topics:
        try:
            if build_round(mode_is_ai, topics, count):
                st.rerun()
        except Exception as e:
            st.error(f"❌ 出錯：{e}")
