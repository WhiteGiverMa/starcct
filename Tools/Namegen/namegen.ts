#!/usr/bin/env bun
/**
 * 星际茶餐厅 · 商号与部队番号生成器（预览版）
 *
 * 运行：
 *   bun Tools/Namegen/namegen.ts
 *   bun Tools/Namegen/namegen.ts --faction 星际茶餐厅 --count 10
 *   bun Tools/Namegen/namegen.ts --faction 星际茶餐厅 --digits chinese --seed 20261105
 *
 * 只依赖 Bun 运行时，不读取游戏文件。词池直接写在下方，改这里就能加词。
 */

// 两字前缀，取自广式茶餐厅常见的成词字号。
const TWO_CHARACTER_PREFIXES = [
    "顺景", "顺兴", "顺意", "顺发", "顺心", "顺记",
    "满盈", "满福", "满庭", "满堂", "满香", "满记",
    "盈丰", "盈泰", "盈门",
    "鸿福", "鸿运", "鸿兴", "鸿记", "鸿发",
    "福满", "福来", "福星", "福记", "福临", "福兴", "福昌", "福源", "福安", "福华",
    "静好", "静雅", "静香", "静园", "静心",
    "兴隆", "兴盛", "兴旺", "兴记", "兴华", "兴发",
    "昌盛", "昌隆", "昌记", "昌华",
    "泰和", "泰兴", "泰昌", "泰记", "泰丰",
    "和记", "和兴", "和顺", "和丰", "和香",
    "益丰", "益记", "益兴",
    "裕丰", "裕记", "裕泰", "裕兴",
    "锦华", "锦记", "锦香", "锦园",
    "金华", "金记", "金凤", "金满", "金兴",
    "银龙", "银记", "银华", "银星",
    "彩云", "彩虹", "彩记",
    "喜乐", "喜庆", "喜盈", "喜记",
    "安乐", "安记", "安泰", "安香",
    "嘉祥", "嘉记", "嘉华",
    "瑞祥", "瑞记", "瑞丰", "瑞兴",
    "德发", "德兴", "德昌", "德和", "德记",
    "旺角", "旺记", "旺发", "旺兴",
    "泉源", "泉记", "香江", "香记", "香园", "香满",
    "鲜美", "鲜记",
    "悦来", "悦记", "悦香",
    "怡和", "怡记", "怡园",
    "雅苑", "雅记", "雅香",
    "新记", "新光", "新发", "新香", "新景",
    "永兴", "永恒", "永发", "永记", "永利",
    "长兴", "长记", "长乐", "长丰",
    "天星", "天香", "天发", "天河",
    "星月", "星辉", "星记", "星港", "星华",
    "月满", "月光", "月记", "月华",
    "海景", "海记", "海港", "海悦",
    "龙凤", "龙记", "龙华", "龙兴",
    "宝华", "宝记", "宝丰", "宝兴",
    "珠光", "珠记", "珠江",
    "玉记", "玉华", "玉泉",
    "荣华", "荣记", "荣兴",
    "华星", "华记", "华丰", "华兴",
    "丽都", "丽华", "丽记",
    "富华", "富记", "富兴",
    "翠华", "翠园", "翠记",
    "乐满", "乐记", "乐香",
    "合兴", "联兴", "同兴", "万兴", "广兴", "民兴", "国兴",
    "大华", "大同", "太平", "平安", "康乐",
    "三宝", "四喜", "五福", "七星", "八珍", "九记", "十全",
    "老友", "街坊", "街角", "巷口",
    "兰芳", "胜香", "杏花", "莲香", "陶陶", "添福", "添喜",
    "甜甜", "点点", "家家", "日日", "时时", "美美", "乐乐", "喜喜", "满满", "盈盈",
    // 科幻味的店号：配「冰室」「茶餐厅」也不会太出戏。
    "星舰", "轨道", "深空", "星环", "陨石", "穹顶",
    "殖民", "废土", "锈港", "霓虹", "曲速", "跃迁", "量子", "等离子",
];

// 三字前缀，老字号、地名与叠字店名。
const THREE_CHARACTER_PREFIXES = [
    "金满堂", "福满门", "喜盈门", "满堂香", "鸿运来", "福临门", "喜临门", "大三元", "新世界",
    "状元坊", "老地方", "天星阁", "明月楼", "彩云间", "龙凤阁", "聚宝盆", "八方来", "四季兴",
    "万年青", "步步香", "家家乐", "日日香", "天天旺", "人人爱", "满庭芳", "桂花香", "甜甜屋",
    "点点甜", "富临门", "金玉堂", "百乐门", "夜来香", "十里香", "一品香",
    "深水埗", "油麻地", "尖沙咀", "铜锣湾",
    // 三字科幻前缀。
    "空间站", "轨道站", "深空站", "殖民站", "着陆场", "陨石带", "废土镇", "锈港区", "穹顶城",
];

// 后缀，广式老铺与星际驿站的混合。
const SUFFIXES = [
    "冰室", "餐室", "餐厅", "茶餐厅", "食肆", "茶楼", "茶室", "茶座", "茶居",
    "酒家", "大酒楼", "粥面家", "饼家", "糖水铺", "冰厅", "咖啡室",
    "食堂", "饭堂", "小馆", "快餐", "酒店", "驿站",
    "星际茶楼", "星际冰室", "星际驿站", "太空餐室", "星港食堂", "轨道茶寮",
    // 科幻味的业态后缀。
    "星际食堂", "轨道食堂", "深空茶寮", "星环茶楼", "太空驿站",
    "星舰食堂", "穹顶茶室", "星门茶室", "轨道驿站", "殖民地茶楼", "废土茶寮", "霓虹餐室",
];

// 部队机关前缀。
const DEPARTMENTS = [
    "国防部", "武装部", "军事委员会", "参谋本部", "总司令部", "联合指挥部",
    "最高指挥部", "作战部", "军务部", "后勤部", "兵役局", "卫戍司令部",
    "战略司令部", "联合作战部", "国防军", "自卫队", "人民军", "革命卫队",
    "军团部", "战备部",
];

// 番号单位与对应的最大序号；序号越大，师旅团的数字范围越像真实编制。
const MILITARY_UNITS = [
    { name: "殖民师", maxSerial: 199 },
    { name: "步兵师", maxSerial: 199 },
    { name: "装甲师", maxSerial: 199 },
    { name: "守备师", maxSerial: 199 },
    { name: "卫戍师", maxSerial: 199 },
    { name: "空降师", maxSerial: 199 },
    { name: "山地师", maxSerial: 199 },
    { name: "炮兵师", maxSerial: 199 },
    { name: "机动师", maxSerial: 199 },
    { name: "合成旅", maxSerial: 299 },
    { name: "重装合成旅", maxSerial: 299 },
    { name: "机步旅", maxSerial: 299 },
    { name: "突击旅", maxSerial: 299 },
    { name: "空降旅", maxSerial: 299 },
    { name: "混成旅", maxSerial: 299 },
    { name: "摩托化旅", maxSerial: 299 },
    { name: "边防旅", maxSerial: 299 },
    { name: "猎兵团", maxSerial: 499 },
    { name: "步兵团", maxSerial: 499 },
    { name: "守备团", maxSerial: 499 },
    { name: "边防团", maxSerial: 499 },
    { name: "特种作战团", maxSerial: 499 },
    { name: "独立团", maxSerial: 499 },
    { name: "骠骑兵团", maxSerial: 499 },
    { name: "龙骑兵团", maxSerial: 499 },
    { name: "炮兵团", maxSerial: 499 },
    { name: "工兵团", maxSerial: 499 },
    { name: "辎重团", maxSerial: 499 },
    { name: "集团军", maxSerial: 99 },
    { name: "远征军", maxSerial: 99 },
    { name: "航空联队", maxSerial: 99 },
    { name: "游击纵队", maxSerial: 99 },
    { name: "特遣舰队", maxSerial: 99 },
    { name: "远征舰队", maxSerial: 99 },
];

const MODIFIERS = ["近卫", "独立", "先锋", "铁血", "荣誉", "功勋", "精锐", "传奇", "钢铁"];

const CHINESE_DIGITS = "零一二三四五六七八九";

interface Options {
    faction: string | null;
    count: number;
    seed: string | null;
    digits: "chinese" | "arabic";
    restaurant: boolean;
    military: boolean;
}

/** FNV-1a，把任意种子字符串转成 32 位整数。 */
function hashSeed(text: string): number {
    let hash = 0x811c9dc5;
    for (let index = 0; index < text.length; index++) {
        hash ^= text.charCodeAt(index);
        hash = Math.imul(hash, 0x01000193);
    }
    return hash >>> 0;
}

/** mulberry32，小、快、对预览足够。 */
function mulberry32(seed: number): () => number {
    let state = seed >>> 0;
    return () => {
        state = (state + 0x6d2b79f5) >>> 0;
        let value = state;
        value = Math.imul(value ^ (value >>> 15), value | 1);
        value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
        return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
}

function pick<T>(items: readonly T[], random: () => number): T {
    return items[Math.floor(random() * items.length)]!;
}

function chance(probability: number, random: () => number): boolean {
    return random() < probability;
}

/** 1..999 转标准中文数字：一百零一、一百一十、九百九十九。 */
function toChineseNumber(value: number): string {
    if (!Number.isInteger(value) || value < 1 || value > 999) {
        throw new RangeError(`番号只支持 1..999，收到 ${value}`);
    }
    if (value < 10) {
        return CHINESE_DIGITS[value]!;
    }
    if (value < 100) {
        const tens = Math.floor(value / 10);
        const ones = value % 10;
        return (tens === 1 ? "" : CHINESE_DIGITS[tens]!) + "十" + (ones === 0 ? "" : CHINESE_DIGITS[ones]!);
    }
    const hundreds = Math.floor(value / 100);
    const rest = value % 100;
    const head = CHINESE_DIGITS[hundreds]! + "百";
    if (rest === 0) {
        return head;
    }
    if (rest < 10) {
        return head + "零" + CHINESE_DIGITS[rest]!;
    }
    if (rest < 20) {
        return head + "一十" + (rest === 10 ? "" : CHINESE_DIGITS[rest % 10]!);
    }
    return head + toChineseNumber(rest);
}

/** 前缀与后缀若共享同一个双字片段，会读成「星港星港食堂」；命中就重抽后缀。 */
function repeatsBigram(prefix: string, suffix: string): boolean {
    for (let index = 0; index + 2 <= prefix.length; index++) {
        if (suffix.includes(prefix.slice(index, index + 2))) {
            return true;
        }
    }
    return false;
}

function generateRestaurantName(random: () => number): string {
    for (let attempt = 0; attempt < 20; attempt++) {
        const prefix = chance(0.35, random)
            ? pick(THREE_CHARACTER_PREFIXES, random)
            : pick(TWO_CHARACTER_PREFIXES, random);
        const suffix = pick(SUFFIXES, random);
        if (!repeatsBigram(prefix, suffix)) {
            return prefix + suffix;
        }
    }
    return pick(TWO_CHARACTER_PREFIXES, random) + pick(SUFFIXES, random);
}

function generateMilitaryName(faction: string, random: () => number, digits: Options["digits"]): string {
    const unit = pick(MILITARY_UNITS, random);
    const serial = 1 + Math.floor(random() * unit.maxSerial);
    const serialText = digits === "chinese" ? toChineseNumber(serial) : String(serial);
    const department = chance(0.6, random) ? pick(DEPARTMENTS, random) : "";
    // 已带「独立」的单位不再叠「独立」修饰；有部门时修饰出现得少一些，名字短一点。
    const modifierChance = department === "" ? 0.4 : 0.15;
    const modifier = !unit.name.includes("独立") && chance(modifierChance, random)
        ? pick(MODIFIERS, random)
        : "";
    return `${faction}${department}${modifier}第${serialText}${unit.name}`;
}

function generateUnique(count: number, create: () => string): string[] {
    const names = new Set<string>();
    const attemptLimit = Math.max(count * 50, 200);
    for (let attempt = 0; attempt < attemptLimit && names.size < count; attempt++) {
        names.add(create());
    }
    return [...names];
}

function printUsage(): void {
    console.log(`星际茶餐厅 · 商号与部队番号生成器

用法：
  bun Tools/Namegen/namegen.ts [选项]

选项：
  --faction <名字>    派系名，用于拼接部队番号，例如 星际茶餐厅
  --count <数量>      每类生成数量，默认 8
  --seed <种子>       固定随机种子，复现同一批名字
  --digits <风格>     番号写法：arabic（默认，第37）或 chinese（第三十七）
  --restaurant-only   只生成茶餐厅商号
  --military-only     只生成部队番号
  -h, --help          显示本帮助

示例：
  bun Tools/Namegen/namegen.ts --faction 星际茶餐厅 --count 10
  bun Tools/Namegen/namegen.ts --faction 星际茶餐厅 --digits chinese --seed 20261105`);
}

function parseArgs(argv: readonly string[]): Options {
    const options: Options = {
        faction: null,
        count: 8,
        seed: null,
        digits: "arabic",
        restaurant: true,
        military: true,
    };
    for (let index = 0; index < argv.length; index++) {
        const argument = argv[index]!;
        switch (argument) {
            case "--faction": {
                const value = argv[++index];
                if (value === undefined) {
                    throw new Error("--faction 缺少参数");
                }
                options.faction = value;
                break;
            }
            case "--count": {
                const value = argv[++index];
                const count = Number(value);
                if (!Number.isInteger(count) || count < 1 || count > 200) {
                    throw new Error("--count 需要 1..200 的整数");
                }
                options.count = count;
                break;
            }
            case "--seed": {
                const value = argv[++index];
                if (value === undefined) {
                    throw new Error("--seed 缺少参数");
                }
                options.seed = value;
                break;
            }
            case "--digits": {
                const value = argv[++index];
                if (value !== "chinese" && value !== "arabic") {
                    throw new Error("--digits 只接受 chinese 或 arabic");
                }
                options.digits = value;
                break;
            }
            case "--restaurant-only":
                options.military = false;
                break;
            case "--military-only":
                options.restaurant = false;
                break;
            case "-h":
            case "--help":
                printUsage();
                process.exit(0);
                break;
            default:
                throw new Error(`未知参数：${argument}`);
        }
    }
    return options;
}

function main(): void {
    let options: Options;
    try {
        options = parseArgs(process.argv.slice(2));
    } catch (error) {
        console.error(`${(error as Error).message}\n`);
        printUsage();
        process.exitCode = 1;
        return;
    }

    const random = options.seed === null
        ? Math.random
        : mulberry32(hashSeed(options.seed));

    if (options.restaurant) {
        const names = generateUnique(options.count, () => generateRestaurantName(random));
        console.log(`茶餐厅商号（${names.length}）`);
        for (const name of names) {
            console.log(`  ${name}`);
        }
    }

    if (options.military) {
        if (options.restaurant) {
            console.log();
        }
        if (options.faction === null) {
            console.log("部队番号");
            console.log("  传 --faction <派系名> 才会生成，例如 --faction 星际茶餐厅");
        } else {
            const names = generateUnique(options.count, () => generateMilitaryName(options.faction!, random, options.digits));
            console.log(`部队番号 · ${options.faction}（${names.length}）`);
            for (const name of names) {
                console.log(`  ${name}`);
            }
        }
    }
}

main();
