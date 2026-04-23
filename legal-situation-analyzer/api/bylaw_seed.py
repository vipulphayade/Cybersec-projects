from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re


LAW_NAME = "Maharashtra Cooperative Housing Society Model Bye-laws"


@dataclass(frozen=True)
class BylawCatalogEntry:
    bylaw_number: str
    section_code: str
    clause_title: str


RAW_CATALOG = """
1|A|Name of the Society
1|B|Procedure for changing the name
1|C|Classification
2|A|Address of the Society
2|B|Intimation of change in the address of the Society
2|C|Procedure for changing the address of the Society
2|D|Exhibition of the name board
3||Interpretations of the words and terms
4||Area of operation of the Society
5||Objects of the Society
6||Affiliation of the Society to other co-operative institutions
7||Different modes of raising the funds of the Society
8||Authorised share capital of the Society
9||Issue of share certificates to the members of the Society
10||Society seal and signatures of office-bearers on each share certificate
11||Restrictions on incurring liabilities of the Society
12|I|How the Reserve Fund shall be constituted
12|II|Appropriation of the amounts to the Reserve Fund of the Society
13|A|Creation of the Repairs and Maintenance Fund by the Society
13|B|Creation of Major Repairs Fund by the Society
13|C|Creation of the Sinking Fund by the Society
13|D|Creation of Education and Training Fund
14|A|Utilisation of the Reserve Fund
14|B|Utilisation of the Repairs and Maintenance Fund by the Society
14|C|Utilisation of Sinking Fund
14|D|Utilisation of Education and Training Fund
15||Modes of investment of funds of the Society
16||Classes of members
17|A|Eligibility of individuals for membership of the Society
17|B|Eligibility of minor or a person of unsound mind for membership of the Society
17|C|Admission of person to society membership subject to the Collector approval
18||Eligibility of corporate bodies for membership of the Society
19|A|Conditions for individuals desiring to be members of the Society
19|B|Conditions of associate membership of the Society
19|C|Conditions of membership for bodies corporate desiring to become member of the Society
20||Conditions for nominal membership of the Society
21||Procedure for disposal of application for membership
22||Rights of members and access to bye-laws and audit materials
23|A|Rights of inspection of documents and getting copies thereof
23|B|Inspection of books and records
24|A|Rights of occupation of flats
25||No rights of membership to an associate member except under Section 27(2) of the Act
26||No right of membership to a nominal member
27|A|Notice of resignation of membership of the Society
27|B|Resignation not to be accepted unless charges of the Society are fully paid
27|C|Communication of the amount of charges of the Society outstanding to the member
27|D|Acceptance of resignation where no charges of the Society are outstanding
27|E|Communication of reasons for rejection of resignation
28||Resignation by an associate member
29||Resignation by a nominal member occupying the flat on behalf of a firm, company or any other body corporate
30||Resignation by a sub-lettee, licensee or caretaker
31||Acquisition of shares and interest of the member in the capital or property of the Society
32||Procedure for nomination by a member and its revocation
33||Recording of nomination or revocation of earlier nomination
34||Transfer of shares and interest of the deceased member in the capital or property of the Society to the nominee
35||Transfer of shares and interest of the deceased member in the capital or property of the Society to the heir
36||Payment of the value of shares and interest of the deceased member to the nominee or nominees
37||Payment of the value of shares and interest of the deceased member to the heir or legal representative
38|A|Notice of transfer of shares and interest in the capital or property of the Society
38|B|Secretary to place such notice before the next Committee meeting
38|C|Informing ineligibility within eight days
38|D|No Objection Certificate not required but may be issued if required within one month
38|E|Documents to be submitted by the transferor and transferee
39|A|Disposal of application for transfer of shares and interest of the member
39|B|Committee or General Body not to ordinarily refuse any application for membership or transfer
39|C|When application for transfer shall be deemed to have been rejected
39|D|Unauthorised transfer null and void
40||Rights of membership since when to be exercised by the transferee
41||Application for exchange of flats by the members of the Society
42||Disposal of application for exchange of flats by the members of the Society
43|A|Sub-letting not permissible except under Society permission
43|B|Application for getting permission to sub-let the flat
44||Restrictions on assignment of occupancy right in the flat
45||Flat to be kept clean
46|A|Additions and alterations in a flat to be carried out with the Committee permission
46|B|Application for permission for additions and alterations in flat
47|A|Examination of flats by Secretary and report about repairs to flats
47|B|Notice to the member about carrying out repair in the flat by the Society at its cost
47|C|Notice to the member for carrying out repairs to the flat at the member cost
48||Restrictions on storing of certain goods
49|A|Not to do anything in a flat causing inconvenience, nuisance or annoyance to other members
49|B|Committee to take action on complaints about violation of the relevant bye-laws
50||Grounds on which a member can be expelled
51|A|Procedure for expulsion of member
51|B|Forfeiture of shares of the expelled member
52||Effect of expulsion on membership of the Society
53||Handling over vacant possession of the flat by the expelled member
54||Acquisition of the shares and interest of the expelled member
55||Eligibility of the expelled member for re-admission to membership of the Society
56||Circumstances under which the person shall cease to be a member of the Society
57||Circumstances under which the person shall cease to be associate member
58||Circumstances under which the person occupying the flat on behalf of the firm or company ceases to be the nominal member
59||Circumstances under which a sub-lettee, licensee or caretaker ceases to be the nominal member
60||Action by the Committee in the case of cessation of membership of the Society
61||Holding of flats by member
62||Liability limited to paid-up share amount
63||Liability of past and deceased member
64||Disposal of application and payment of value of shares or interest of a member or past member
65||Composition of the charges of the Society
66||Break-up of the service charges of the Society
67||Sharing of the Society charges by the members
68||Repairs and maintenance to be carried out by the Society
69||Payment of the Society charges
70||Review of the cases of defaults in payment of the charges of the Society
71||Interest on the defaulted charges
72||Incorporation of duties and powers of the Society
73||Common seal
74||Charges and set-off in respect of shares and interest of a member of the Society
75|A|Flat purchased is deemed to have been allotted
75|B|Policy of allotment of flats
75|C|Cancellation of allotment of flats
75|D|Handling over possession of flats
75|E|Change of user not permissible without the sanction of the Committee
76||Society to carry out structural audit
77||To obtain certificate of possession from the allottee
78|A|Policy of allotment of parking slots
78|B|Restriction on use of parking slots
79||Marking of parking spaces of stilts
80||Eligibility for allotment of stilts or parking slots
81||If more eligible members and less parking slots
82||Applications for allotment of parking slots
83||Payment of charges for parking of vehicles
84||Parking of other vehicles
85||Holding of the first General Meeting within the stipulated period
86||Calling the first General Meeting by the Registering Authority
87||Period of notice for the first General Meeting
88|A|Functions of the first General Meeting
88|B|Nomination of a provisional committee by the Registering Authority
89||Recording of minutes at the first General Meeting
90||Handing over records by the Chief Promoter of the Society
91||Powers of the Provisional Committee
92||Period of office of the Provisional Committee
93||Handing over charge by the Provisional Committee
94||Period within which Annual General Body Meeting should be held
95||Functions of the Annual General Body Meeting of the Society
96||When a Special General Meeting should be called
97||Fixing date, time and place for a requisitioned Special General Meeting
98||Notice of a General Body Meeting
99||Period of notice of a General Body Meeting
100||Quorum for the General Body Meeting
101||Holding of the adjourned General Body Meeting
102||Postponement of the General Body Meeting which cannot complete the business on the agenda
103||Chairman of the Society to preside over all General Body Meetings
104||Restrictions on attending a General Body Meeting by a proxy
105||Voting right of a member
106||One member one vote
107||How decisions shall be taken
108||Recording of the minutes of the General Body Meetings
109||Cancellation of the previous resolution of the General Body Meeting
110||General Body Meeting to be the supreme authority
111||Management of the Society to vest in the Committee
112||Exercise of powers by the Committee
113||Opening of banking account
114||Strength of the Committee
115||Election of the Committee
116||Prohibition against being interested in the Society
117||Disqualification for being elected on the Committee
118||Constitution of the Committee
119|A|Cessation of a member of the Committee
119|B|Intimation of cessation of membership of the Committee
120||Restrictions on being present at consideration of a matter in which a Committee member is interested
121||Period of office of the elected Committee
122|A|First meeting of new Committee
122|B|Issue of notice of the first meeting of the newly elected Committee
123||Custody of the records of the Society
124||Handling over charge by the outgoing Committee
125||Election of office bearers of the Society
126||Quorum for Committee meetings
127||Number of Committee meetings to be held in a month
128||Casual vacancies in the Committee to be filled by co-option
129||Period of office of the member co-opted by the Committee
130||Resignation of Committee member of the Society
131||Resignation of office-bearer of the Committee
132||Notice of meeting of the Committee
133||Chairman of the Society to preside over the meetings of the Committee
134||One member one vote and decision by majority of the Committee
135||Special meeting of the Committee at the instance of one-third members or by the Chairman
136||Attending meetings of the Committee and recording their minutes by the Secretary
137||Joint and several liability of the members of the Committee
138||Powers, functions and duties of the Committee
139||Powers of the Chairman of the Society
140||Functions of the Secretary
141||Books of account, registers and other books to be maintained
142||Other records to be maintained separately
143||Secretary to maintain and keep up to date the account books
144||Cash on hand limit
145||Payment beyond certain limit by cheque or approved banking mode
146||Finalisation of accounts
147||Security by the employees
148|A|Contribution to the statutory Reserve Fund of the Society
148|B|Distribution of the remaining profit of the Society
149||Amounts which could be written off
150||Procedure to be followed before writing off any account
151||Appointment of auditors
152||Secretary to produce books, registers and records to internal or statutory auditors
153||Preparation of audit rectification report
154|A|Necessary steps for conveyance or deemed conveyance
154|B|Finalisation of deed of conveyance
154|C|Execution of deed of conveyance
155||Committee responsibility to maintain the Society property
156||Inspection of Society property for repair
157||Committee to execute repairs and maintenance of the property of the Society
158||Work on repairs and redevelopment
159|A|Various items of repairs and maintenance to be carried out by the Society at its cost
159|B|Repairs by the members at their cost
160||Building insurance
161||Trees in the compound of the Society
162||Modes of communication of notices, resolutions and decisions
163||Accounting year
164||Notice board
165||Penalties for breaches
166||Alteration or amendment of bye-laws
167||Operation of lifts, solar water heaters and similar common systems
168||Restriction on playing games
169||Prohibition on letting out open or common spaces
170||Temporary use of the terrace or open space by any member
171||Fees for supply of copies of documents
172||Complaint application to be submitted to the Society
173||Committee action on the complaint application
174|A|If action is not taken within stipulated period complaint may be made to the Registrar
174|B|If action is not taken within stipulated period complaint may be made to the Co-operative Court
174|C|If action is not taken within stipulated period complaint may be made to the Civil Court
174|D|If action is not taken within stipulated period complaint may be made to the Municipal Corporation or local authority
174|E|If action is not taken within stipulated period complaint may be made to the Police
174|F|If action is not taken within stipulated period complaint may be made to the General Body Meeting
174|G|If action is not taken within stipulated period complaint may be made to the Federation
175|A|Redevelopment of the property or building of the Society
175|B|Redevelopment strictly as per directives dated 3 January 2009
175|C|Increase of authorised share capital if members increase after redevelopment
""".strip()


TOPIC_KEYWORDS = {
    "parking": ["parking", "vehicle", "stilt parking", "parking slot", "allotment", "parking dispute"],
    "membership": ["membership", "member", "associate member", "nominal member", "admission", "eligibility"],
    "transfer": ["transfer", "shares", "nominee", "heir", "deceased member", "transferee"],
    "committee": ["committee", "office bearer", "quorum", "meeting", "resolution", "management"],
    "general meeting": ["general body", "agm", "sgm", "meeting notice", "quorum", "minutes"],
    "charges": ["charges", "maintenance charges", "service charges", "default", "interest"],
    "fund": ["fund", "reserve fund", "sinking fund", "investment", "society finances"],
    "repair": ["repairs", "maintenance", "structural audit", "repair work", "building upkeep"],
    "redevelopment": ["redevelopment", "developer", "conveyance", "deemed conveyance", "building redevelopment"],
    "audit": ["audit", "auditor", "books of account", "rectification report", "financial records"],
    "complaint": ["complaint", "grievance", "redressal", "registrar", "co-operative court"],
    "flat": ["flat", "occupation", "allotment", "possession", "user change"],
}


SPECIAL_OVERRIDES = {
    ("14", "A"): {
        "explanation": (
            "Bye-law 14(a) treats the Reserve Fund as a protected society fund "
            "meant for repairs, maintenance, and renewals of society property."
        ),
        "conditions": [
            "Use should remain tied to the object of the Reserve Fund under the registered bye-laws.",
            "Supporting committee records and fund ledger entries should exist.",
            "The expenditure should relate to society property repairs, maintenance, or renewals.",
        ],
        "possible_challenges": [
            "Reserve Fund used for expenses unrelated to society property repairs or renewals",
            "Missing fund ledger support or inadequate committee records",
            "Use inconsistent with the registered bye-laws or approved budget process",
        ],
        "related_statutes": [
            "Maharashtra Co-operative Societies Act, 1960",
            "Maharashtra Co-operative Societies Rules, 1961",
            "Maharashtra Co-operative Societies Act Section 81 Audit",
            "Maharashtra Co-operative Societies Act Section 83 Registrar Inquiry",
            "Maharashtra Co-operative Societies Act Section 91 Cooperative Court Disputes",
        ],
    },
    ("14", "B"): {
        "explanation": (
            "Bye-law 14(b) covers use of the Repairs and Maintenance Fund for "
            "routine upkeep, repairs, and renewals connected with society property."
        ),
    },
    ("14", "C"): {
        "explanation": (
            "Bye-law 14(c) is generally read as limiting the Sinking Fund to "
            "major structural repairs, heavy renewals, or reconstruction-related "
            "expenditure rather than ordinary recurring maintenance."
        ),
        "conditions": [
            "General Body approval should be checked where required by the registered bye-laws and society process.",
            "Architect or structural engineer documentation should support the structural or major repair nature of the work.",
            "A proper committee or General Body resolution and financial record trail should exist.",
        ],
        "possible_challenges": [
            "Sinking Fund used for routine maintenance instead of major structural repairs or reconstruction",
            "No structural report, architect certificate, or engineering support",
            "No General Body approval or inadequate meeting record where such approval is expected",
        ],
        "related_statutes": [
            "Maharashtra Co-operative Societies Act, 1960",
            "Maharashtra Co-operative Societies Rules, 1961",
            "Maharashtra Co-operative Societies Act Section 81 Audit",
            "Maharashtra Co-operative Societies Act Section 83 Registrar Inquiry",
            "Maharashtra Co-operative Societies Act Section 88 Assessment of Damages for Misapplication",
            "Maharashtra Co-operative Societies Act Section 91 Cooperative Court Disputes",
        ],
    },
    ("14", "D"): {
        "explanation": (
            "Bye-law 14(d) links the Education and Training Fund to cooperative "
            "education and training of members, committee members, officers, and employees."
        ),
        "related_statutes": [
            "Maharashtra Co-operative Societies Act, 1960",
            "Maharashtra Co-operative Societies Rules, 1961",
            "Maharashtra Co-operative Societies Act Section 24A Co-operative Education and Training",
            "Maharashtra Co-operative Societies Act Section 81 Audit",
            "Maharashtra Co-operative Societies Act Section 91 Cooperative Court Disputes",
        ],
    },
    ("78", "A"): {
        "explanation": (
            "Bye-law 78(a) addresses parking-slot allocation policy and expects the "
            "society to follow an adopted policy rather than ad hoc or discriminatory allotment."
        ),
        "conditions": [
            "A parking policy should be approved and recorded through the competent society process.",
            "Implementation should be documented by the Committee.",
            "Allocation criteria should be applied consistently to similarly placed members.",
        ],
        "possible_challenges": [
            "Arbitrary parking allocation",
            "Discrimination between members",
            "No recorded parking policy or inconsistent implementation",
        ],
    },
    ("174", "A"): {
        "explanation": (
            "Bye-law 174(a) indicates that a member may approach the Registrar if the "
            "society does not act on a complaint within the prescribed internal process."
        ),
    },
    ("174", "B"): {
        "explanation": (
            "Bye-law 174(b) points to the Co-operative Court as a possible forum when "
            "the dispute falls within co-operative jurisdiction and internal action is ineffective."
        ),
        "related_statutes": [
            "Maharashtra Co-operative Societies Act, 1960",
            "Maharashtra Co-operative Societies Act Section 91 Cooperative Court Disputes",
            "Registered bye-laws of the Society",
        ],
    },
    ("175", "A"): {
        "explanation": (
            "Bye-law 175(a) governs redevelopment of society property or buildings and "
            "is generally read with redevelopment directives, member approvals, and documented process safeguards."
        ),
        "conditions": [
            "Society redevelopment process should follow the registered bye-laws and applicable government directives.",
            "Meeting notices, resolutions, bid comparison, and member decision records should be preserved.",
            "Developer terms, technical reports, and project documents should be documented and traceable.",
        ],
        "possible_challenges": [
            "Redevelopment initiated without proper member approval process",
            "Insufficient transparency in developer selection or terms",
            "Departure from applicable redevelopment directives or registered bye-laws",
        ],
    },
}


def parse_catalog() -> list[BylawCatalogEntry]:
    entries: list[BylawCatalogEntry] = []
    for line in RAW_CATALOG.splitlines():
        bylaw_number, section_code, clause_title = [part.strip() for part in line.split("|")]
        entries.append(BylawCatalogEntry(bylaw_number, section_code, clause_title))
    return entries


def get_chapter_title(bylaw_number: int) -> str:
    ranges = [
        (1, 2, "Preliminary"),
        (3, 3, "Interpretations"),
        (4, 4, "Area of Operation"),
        (5, 5, "Objects"),
        (6, 6, "Affiliation"),
        (7, 15, "Funds, Their Utilisation and Investment"),
        (16, 44, "Members, Their Rights, Responsibilities and Liabilities"),
        (45, 64, "Responsibilities and Liabilities of Members"),
        (65, 71, "Levy of Charges of the Society"),
        (72, 84, "Incorporation of Duties and Powers of the Society"),
        (85, 109, "General Meetings"),
        (110, 140, "Management of the Affairs of the Society"),
        (141, 147, "Maintenance of Books of Account and Registers"),
        (148, 148, "Appropriation of Profits"),
        (149, 150, "Write Off of Irrecoverable Dues"),
        (151, 153, "Audit of Accounts of the Society"),
        (154, 161, "Conveyance, Repairs and Maintenance of Property"),
        (162, 171, "Other Miscellaneous Matters"),
        (172, 174, "Redressal of Members Complaints"),
        (175, 175, "Redevelopment"),
    ]
    for start, end, title in ranges:
        if start <= bylaw_number <= end:
            return title
    return "Model Bye-laws"


def normalize_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(token) > 2]


def infer_topics(clause_title: str, chapter_title: str) -> list[str]:
    source = f"{clause_title} {chapter_title}".lower()
    topics = []
    for topic in TOPIC_KEYWORDS:
        if topic in source:
            topics.append(topic)
    if "member" in source or "membership" in source:
        topics.append("membership")
    if "meeting" in source:
        topics.append("general meeting" if "general" in source else "committee")
    if "parking" in source:
        topics.append("parking")
    if "repair" in source or "maintenance" in source or "structural" in source:
        topics.append("repair")
    if "complaint" in source or "grievance" in source:
        topics.append("complaint")
    if "audit" in source or "account" in source or "fund" in source:
        topics.append("audit" if "audit" in source or "account" in source else "fund")
    if "redevelopment" in source or "conveyance" in source:
        topics.append("redevelopment")
    return list(dict.fromkeys(topics))


def infer_primary_topic(clause_title: str, chapter_title: str) -> str:
    topics = infer_topics(clause_title, chapter_title)
    return topics[0] if topics else "society governance"


def build_keywords(entry: BylawCatalogEntry, chapter_title: str) -> list[str]:
    tokens = normalize_tokens(entry.clause_title)
    phrases = {entry.clause_title.lower(), chapter_title.lower(), f"bye-law {entry.bylaw_number}".lower()}
    if entry.section_code:
        phrases.add(f"bye-law {entry.bylaw_number}({entry.section_code.lower()})")
        phrases.add(f"{entry.bylaw_number}{entry.section_code.lower()}")

    for topic in infer_topics(entry.clause_title, chapter_title):
        phrases.update(TOPIC_KEYWORDS[topic])

    phrases.update(tokens[:8])
    return sorted(phrase.strip() for phrase in phrases if phrase.strip())


def format_bylaw_label(entry: BylawCatalogEntry) -> str:
    return (
        f"Bye-law {entry.bylaw_number}({entry.section_code.lower()})"
        if entry.section_code
        else f"Bye-law {entry.bylaw_number}"
    )


def default_content(entry: BylawCatalogEntry, chapter_title: str) -> str:
    bylaw_label = format_bylaw_label(entry)
    return (
        f"{bylaw_label} deals with {entry.clause_title.lower()} and expects the "
        f"society to follow the registered bye-laws, the Act, and the proper "
        f"society process on this subject."
    )


def default_explanation(entry: BylawCatalogEntry, chapter_title: str) -> str:
    section_label = format_bylaw_label(entry)
    return (
        f"{section_label} is about {entry.clause_title.lower()}. "
        f"In simple terms, it tells the society how this issue should normally "
        f"be handled so decisions are recorded, fair, and consistent."
    )


def _condition(requirement: str, plain_explanation: str) -> dict[str, str]:
    return {
        "requirement": requirement,
        "plain_explanation": plain_explanation,
    }


def default_conditions(entry: BylawCatalogEntry, chapter_title: str) -> list[dict[str, str]]:
    conditions = [
        _condition(
            "Registered bye-laws and legal process must be followed",
            "The society should act according to its registered bye-laws, the Co-operative Societies Act, and the Rules that apply.",
        ),
        _condition(
            "Records and documents should be maintained",
            "Notices, resolutions, registers, and supporting papers should be kept so the decision can be verified later.",
        ),
    ]

    title = entry.clause_title.lower()

    if "meeting" in title or "general body" in title:
        conditions.append(
            _condition(
                "Meeting notice, quorum, and minutes should be proper",
                "The meeting must be called correctly, enough members must attend, and the decision should be written in the minutes.",
            )
        )
    if "committee" in title:
        conditions.append(
            _condition(
                "Committee decision should be recorded",
                "The Committee should decide this in a proper meeting and record the decision in its resolution book.",
            )
        )
    if any(term in title for term in ["membership", "member", "associate", "nominal", "nominee", "heir"]):
        conditions.append(
            _condition(
                "Eligibility documents should support the action",
                "The member should provide the documents needed to prove eligibility, identity, nomination, or succession.",
            )
        )
    if any(term in title for term in ["transfer", "shares", "interest", "nomination"]):
        conditions.append(
            _condition(
                "Transfer or succession papers should be complete",
                "The society should have the required forms and proof before it updates shares, nomination, or transfer records.",
            )
        )
    if any(term in title for term in ["parking", "allotment"]):
        conditions.append(
            _condition(
                "Allocation policy should be applied uniformly",
                "The same parking or allotment rules should be applied fairly to members in similar situations.",
            )
        )
    if any(term in title for term in ["fund", "charges", "audit", "account", "bank"]):
        conditions.append(
            _condition(
                "Financial trail should be available",
                "The society should be able to show bills, vouchers, ledger entries, approvals, and other financial records for the decision.",
            )
        )
    if any(term in title for term in ["repair", "maintenance", "structural", "redevelopment", "conveyance"]):
        conditions.append(
            _condition(
                "Technical or property documents may be needed",
                "For repairs, maintenance, conveyance, or redevelopment, the society should have the necessary technical reports, work papers, or property records.",
            )
        )

    return conditions[:4]


def normalize_conditions(conditions: list) -> list[dict[str, str]]:
    normalized = []
    for item in conditions:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            requirement_text = str(item)
            lowered = requirement_text.lower()
            if "general body" in lowered:
                plain = "This usually means the decision should be approved in a meeting of all society members."
            elif "architect" in lowered or "structural engineer" in lowered:
                plain = "A qualified architect or structural engineer should confirm that the work or decision is actually necessary."
            elif "committee" in lowered and "resolution" in lowered:
                plain = "The Committee should record the decision properly in its meeting minutes or resolution book."
            elif "documents" in lowered or "records" in lowered:
                plain = "The society should keep written records so members can verify why the decision was taken."
            elif "policy" in lowered:
                plain = "The society should have a clear written rule and apply it equally to everyone."
            elif "financial" in lowered or "ledger" in lowered or "voucher" in lowered:
                plain = "Bills, account entries, and supporting papers should exist to show how money was used."
            else:
                plain = "This requirement should be checked in the society records before the decision is treated as valid."
            normalized.append(
                _condition(
                    requirement_text,
                    plain,
                )
            )
    return normalized


def default_challenges(entry: BylawCatalogEntry, chapter_title: str) -> list[str]:
    challenges = [
        "Action taken without following the registered bye-laws or required internal process",
        "Inadequate notice, record trail, or supporting documentation",
    ]

    title = entry.clause_title.lower()

    if "parking" in title:
        challenges.append("Arbitrary or discriminatory parking treatment")
    if "meeting" in title or "committee" in title or "general body" in title:
        challenges.append("Lack of quorum, improper notice, or defective minutes")
    if any(term in title for term in ["fund", "charges", "audit", "account"]):
        challenges.append("Financial action not supported by proper records, approvals, or account classification")
    if any(term in title for term in ["repair", "maintenance", "redevelopment", "conveyance"]):
        challenges.append("Insufficient technical, contractual, or property documentation")
    if any(term in title for term in ["membership", "transfer", "nomination", "heir", "associate", "nominal"]):
        challenges.append("Eligibility, succession, or transfer documentation disputed or incomplete")

    return challenges[:4]


def default_related_statutes(entry: BylawCatalogEntry, chapter_title: str) -> list[str]:
    references = [
        "Maharashtra Co-operative Societies Act, 1960",
        "Maharashtra Co-operative Societies Rules, 1961",
        "Registered bye-laws of the Society",
    ]

    title = entry.clause_title.lower()
    chapter = chapter_title.lower()

    if any(term in title for term in ["fund", "charges", "audit", "account", "bank", "profit", "write off"]):
        references.extend(
            [
                "Maharashtra Co-operative Societies Act Section 81 Audit",
                "Maharashtra Co-operative Societies Act Section 83 Registrar Inquiry",
            ]
        )
    if "complaint" in title or "court" in title or "registrar" in title or "redressal" in chapter:
        references.append("Maharashtra Co-operative Societies Act Section 91 Cooperative Court Disputes")
    if "committee" in title or "management" in chapter or "general body" in title or "meeting" in title:
        references.append("Maharashtra Co-operative Societies Act governance provisions for committee and meetings")
    if "training" in title or "education" in title:
        references.append("Maharashtra Co-operative Societies Act Section 24A Co-operative Education and Training")

    return list(dict.fromkeys(references))


def default_example(entry: BylawCatalogEntry, chapter_title: str) -> str:
    title = entry.clause_title.lower()
    if "parking" in title:
        return "Example: two members claim the same parking slot, so the society must use its approved parking policy instead of choosing arbitrarily."
    if "sinking fund" in title:
        return "Example: the society uses sinking fund for ordinary painting work. Members may question this if the fund should be reserved for major structural work."
    if "membership" in title or "member" in title:
        return "Example: a buyer applies to become a member after purchasing a flat, and the society checks the required documents before admitting the person."
    if "meeting" in title:
        return "Example: an AGM decision may be challenged if the notice was not sent properly or if the required quorum was missing."
    if "complaint" in title or "registrar" in title or "court" in title:
        return "Example: a member complains to the society first, and if there is no response, the member moves to the next forum allowed under the bye-laws."
    if "repair" in title or "maintenance" in title:
        return "Example: the society arranges repair work for common property and keeps the estimate, approval, and work records."
    return f"Example: a member raises an issue about {entry.clause_title.lower()}, and the society should follow the recorded rule and procedure before acting."


def build_relations(dataset: list[dict]) -> list[dict]:
    relations: list[dict] = []
    topic_groups: dict[str, list[dict]] = {}
    for entry in dataset:
        topic_groups.setdefault(entry["topic"], []).append(entry)

    for items in topic_groups.values():
        items.sort(key=lambda item: (int(item["section"]), item["subsection"] or ""))
        for index, item in enumerate(items):
            for neighbor_index in (index - 1, index + 1):
                if 0 <= neighbor_index < len(items):
                    neighbor = items[neighbor_index]
                    if item["section"] == neighbor["section"] and item["subsection"] == neighbor["subsection"]:
                        continue
                    relations.append(
                        {
                            "source_section": item["section"],
                            "source_subsection": item["subsection"],
                            "target_section": neighbor["section"],
                            "target_subsection": neighbor["subsection"],
                        }
                    )
    deduped = []
    seen = set()
    for relation in relations:
        key = tuple(relation.values())
        if key not in seen:
            seen.add(key)
            deduped.append(relation)
    return deduped


def build_dataset() -> list[dict]:
    dataset = []
    for entry in parse_catalog():
        chapter_title = get_chapter_title(int(entry.bylaw_number))
        record = {
            "law_name": LAW_NAME,
            "section": entry.bylaw_number,
            "subsection": entry.section_code.lower(),
            "title": entry.clause_title,
            "topic": infer_primary_topic(entry.clause_title, chapter_title),
            "keywords": build_keywords(entry, chapter_title),
            "content": default_content(entry, chapter_title),
            "explanation": default_explanation(entry, chapter_title),
            "example": default_example(entry, chapter_title),
            "conditions_required": default_conditions(entry, chapter_title),
            "possible_challenges": default_challenges(entry, chapter_title),
            "related_statutes": default_related_statutes(entry, chapter_title),
            "chapter_title": chapter_title,
        }
        override = SPECIAL_OVERRIDES.get((entry.bylaw_number, entry.section_code))
        if override:
            record.update(override)
        record["conditions_required"] = normalize_conditions(
            record.get("conditions_required") or record.get("conditions", [])
        )
        record.pop("conditions", None)
        dataset.append(record)
    return dataset


def write_dataset_json(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(build_dataset(), indent=2), encoding="utf-8")
    return output_path
