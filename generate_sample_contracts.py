"""
Generates 5 sample contract PDFs for testing ClauseSense.
Each contract is subtly adversarial — risks are real but hidden in legalese.

Run:  python generate_sample_contracts.py
Output: sample_contracts/ directory with 5 PDFs
"""

import os
from fpdf import FPDF

OUTPUT_DIR = "sample_contracts"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# PDF builder helper
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Replace characters outside Latin-1 with safe ASCII equivalents."""
    replacements = {
        "\u2014": " - ",   # em dash
        "\u2013": " - ",   # en dash
        "\u2018": "'",     # left single quote
        "\u2019": "'",     # right single quote
        "\u201c": '"',     # left double quote
        "\u201d": '"',     # right double quote
        "\u2026": "...",   # ellipsis
        "\u00a0": " ",     # non-breaking space
        "\u2022": "-",     # bullet
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


class ContractPDF(FPDF):
    def __init__(self, title: str, parties: str):
        super().__init__()
        self._doc_title = _clean(title)
        self._doc_parties = _clean(parties)
        self.set_margins(25, 20, 25)
        self.set_auto_page_break(auto=True, margin=20)
        self.add_page()
        self._draw_header()

    def _draw_header(self):
        self.set_font("Helvetica", "B", 15)
        self.multi_cell(0, 8, self._doc_title, align="C")
        self.ln(2)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 5, self._doc_parties, align="C")
        self.ln(4)
        self.set_draw_color(100, 100, 100)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)

    def section(self, heading: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 10)
        self.multi_cell(0, 6, _clean(heading))
        self.set_font("Helvetica", "", 9)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 5, _clean(text))
        self.ln(1)

    def save(self, filename: str):
        path = os.path.join(OUTPUT_DIR, filename)
        self.output(path)
        print(f"  Written: {path}")


def write(pdf: ContractPDF, heading: str, text: str):
    pdf.section(heading)
    pdf.body(text)


# ===========================================================================
# CONTRACT 1 — SaaS / Software
# Persona: SaaS Procurement Specialist
# Traps: weak SLA, mid-term price hikes, vendor IP grab on integrations,
#         90-day data export window, no usage-audit rights
# ===========================================================================

def make_saas_contract():
    pdf = ContractPDF(
        title="CloudVault Pro — Subscription Services Agreement",
        parties="Between CloudVault Technologies, Inc. ('Vendor') and Customer ('Subscriber')\n"
                "Effective Date: January 1, 2025  |  Initial Term: 24 Months"
    )

    write(pdf, "1. Definitions",
          "1.1 'Service' means the CloudVault Pro cloud storage, backup, and data management "
          "platform made available by Vendor via the internet.\n"
          "1.2 'Customer Data' means data uploaded by Subscriber to the Service.\n"
          "1.3 'Aggregated Data' means data derived from Customer Data that has been de-identified "
          "such that it cannot reasonably identify Subscriber or any individual. Aggregated Data "
          "is the sole and exclusive property of Vendor.\n"
          "1.4 'Maintenance Window' means any period, scheduled or unscheduled, during which "
          "Vendor performs updates, patches, or infrastructure work on the Service.")

    write(pdf, "2. Service Levels and Uptime",
          "2.1 Vendor shall use commercially reasonable efforts to make the Service available "
          "99.5% of the time in any given calendar month ('Uptime Commitment'), measured "
          "excluding Maintenance Windows.\n"
          "2.2 Maintenance Windows are not subject to the Uptime Commitment and may be "
          "scheduled by Vendor at any time upon 4 hours' notice to Subscriber.\n"
          "2.3 In the event Vendor fails to meet the Uptime Commitment in a given month, "
          "Subscriber's sole remedy shall be a service credit equal to 5% of that month's "
          "pro-rated subscription fee, applicable only to the following invoice cycle. "
          "Service credits are non-transferable and have no cash value.\n"
          "2.4 Subscriber must submit a credit request in writing within 15 days of the "
          "affected month; failure to do so constitutes a waiver of any credit for that period.")

    write(pdf, "3. Fees and Pricing",
          "3.1 Subscriber shall pay the fees set forth in the applicable Order Form.\n"
          "3.2 Vendor reserves the right to adjust subscription fees upon no less than "
          "30 days' written notice to Subscriber. Fee increases shall not exceed 15% above "
          "the then-current fees per 12-month period. Continued use of the Service after "
          "the effective date of the adjustment constitutes acceptance of the new fees.\n"
          "3.3 All usage metrics used to calculate any usage-based charges (storage consumed, "
          "API calls, seats) shall be determined solely by Vendor's internal monitoring systems, "
          "whose measurements shall be deemed conclusive and binding.\n"
          "3.4 Invoices are due net-15 from date of issue. Late payments accrue interest at "
          "1.5% per month or the maximum rate permitted by law, whichever is lower.")

    write(pdf, "4. Intellectual Property",
          "4.1 As between the parties, Subscriber retains all right, title, and interest in "
          "Customer Data.\n"
          "4.2 Vendor retains all right, title, and interest in the Service, including its "
          "underlying technology, APIs, SDKs, and documentation.\n"
          "4.3 Any integration, plugin, workflow automation, or connector developed by "
          "Subscriber or its contractors that interfaces with or is built upon Vendor's API "
          "or SDK ('API Derivative Work') shall be jointly owned by Vendor and Subscriber, "
          "with Vendor having the right to commercialise such API Derivative Works without "
          "Subscriber's consent and without any accounting or royalty to Subscriber.\n"
          "4.4 Subscriber grants Vendor a perpetual, irrevocable, royalty-free licence to use "
          "Aggregated Data for any purpose including product development, benchmarking, "
          "marketing, and sale to third parties.")

    write(pdf, "5. Term, Termination, and Data Portability",
          "5.1 This Agreement commences on the Effective Date and continues for the Initial "
          "Term. It will automatically renew for successive 12-month terms unless either "
          "party provides written notice of non-renewal at least 60 days before the end "
          "of the then-current term.\n"
          "5.2 Subscriber may terminate this Agreement for material breach only if such "
          "breach remains uncured for 45 days following written notice.\n"
          "5.3 Vendor may terminate this Agreement for convenience upon 30 days' written "
          "notice to Subscriber.\n"
          "5.4 Upon expiration or termination, Subscriber may request an export of Customer "
          "Data in Vendor's standard export format within 90 days of the termination date. "
          "After such 90-day window, Vendor shall have no obligation to retain Customer Data "
          "and may delete it without further notice. Vendor does not guarantee that exported "
          "data will be in a format compatible with any third-party system.\n"
          "5.5 Vendor shall have no obligation to provide Customer Data in any format other "
          "than Vendor's proprietary backup archive format (.cvpak).")

    write(pdf, "6. Limitation of Liability",
          "6.1 IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, "
          "SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES.\n"
          "6.2 VENDOR'S AGGREGATE LIABILITY TO SUBSCRIBER FOR ANY AND ALL CLAIMS ARISING "
          "UNDER OR RELATED TO THIS AGREEMENT SHALL NOT EXCEED THE TOTAL FEES PAID BY "
          "SUBSCRIBER IN THE THREE (3) MONTHS IMMEDIATELY PRECEDING THE CLAIM.\n"
          "6.3 THE FOREGOING LIMITATIONS SHALL APPLY REGARDLESS OF THE FORM OF ACTION "
          "AND WHETHER VENDOR HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.")

    write(pdf, "7. Confidentiality",
          "7.1 Each party agrees to maintain the confidentiality of the other's Confidential "
          "Information using at least the same care it uses to protect its own confidential "
          "information (but no less than reasonable care).\n"
          "7.2 'Confidential Information' of Vendor includes the Service's pricing, technical "
          "architecture, and all non-public product roadmap information.")

    write(pdf, "8. Governing Law and Dispute Resolution",
          "8.1 This Agreement shall be governed by the laws of the State of Delaware.\n"
          "8.2 Any dispute shall be resolved by binding arbitration administered by JAMS "
          "under its Streamlined Arbitration Rules. Arbitration shall be conducted in "
          "San Francisco, California. The arbitrator's award shall be final and binding, "
          "and judgment may be entered in any court of competent jurisdiction.\n"
          "8.3 Each party waives any right to a jury trial.")

    write(pdf, "9. Miscellaneous",
          "9.1 Vendor may modify this Agreement at any time by posting the revised terms "
          "at its website and providing Subscriber with 14 days' notice by email. Continued "
          "use of the Service constitutes acceptance.\n"
          "9.2 Vendor may assign this Agreement to any successor in connection with a merger, "
          "acquisition, or sale of substantially all of its assets without Subscriber's consent. "
          "Subscriber may not assign this Agreement without Vendor's prior written consent.")

    pdf.save("saas_cloudvault_pro.pdf")


# ===========================================================================
# CONTRACT 2 — Standard SMB
# Persona: Balanced Legal Ops / Standard SMB reviewer
# Traps: customer-cannot-terminate-for-convenience, $500 liability cap,
#         one-sided indemnity, net-15 + 3% late fee, no breach notification
# ===========================================================================

def make_smb_contract():
    pdf = ContractPDF(
        title="Managed IT Services Agreement",
        parties="Between PrimeNet Solutions LLC ('Service Provider') and Client\n"
                "Effective Date: March 1, 2025  |  Term: 12 Months"
    )

    write(pdf, "1. Services",
          "1.1 Service Provider agrees to furnish the managed IT services described in "
          "Schedule 1 attached hereto ('Services'), including network monitoring, helpdesk "
          "support (business hours, 9am–5pm local time), and monthly patch management.\n"
          "1.2 Service Provider reserves the right to modify the scope of Services with "
          "30 days' written notice to Client. Client's continued use of Services following "
          "such notice constitutes acceptance of the modified scope.")

    write(pdf, "2. Fees and Payment",
          "2.1 Client shall pay Service Provider the monthly retainer fee set forth in "
          "Schedule 2 ('Fees').\n"
          "2.2 Invoices are due and payable within 15 days of the invoice date.\n"
          "2.3 Any amounts not paid when due shall bear interest at the rate of 3% per month "
          "compounded monthly, or the highest rate permitted by applicable law, whichever is less.\n"
          "2.4 Service Provider may suspend Services immediately and without notice if any "
          "invoice remains unpaid for more than 10 days after the due date, and such suspension "
          "shall not constitute a breach of this Agreement by Service Provider.")

    write(pdf, "3. Term and Termination",
          "3.1 This Agreement shall commence on the Effective Date and continue for the "
          "Initial Term of twelve (12) months. Upon expiration of the Initial Term, this "
          "Agreement will automatically renew for successive 12-month renewal terms unless "
          "Client provides written notice of non-renewal by certified mail no less than "
          "60 days prior to the end of the then-current term.\n"
          "3.2 Client may terminate this Agreement prior to the end of a term only upon a "
          "material breach by Service Provider that remains uncured for 30 days after "
          "written notice specifying the breach in reasonable detail.\n"
          "3.3 Service Provider may terminate this Agreement for convenience upon 30 days' "
          "written notice to Client, or immediately upon written notice if Client fails to "
          "pay any amount when due.\n"
          "3.4 Upon termination, Client shall pay all fees accrued through the termination "
          "date plus a termination fee equal to 50% of the remaining fees due for the "
          "unexpired portion of the then-current term.")

    write(pdf, "4. Limitation of Liability",
          "4.1 THE TOTAL AGGREGATE LIABILITY OF SERVICE PROVIDER TO CLIENT FOR ANY AND ALL "
          "CLAIMS ARISING OUT OF OR RELATED TO THIS AGREEMENT, WHETHER IN CONTRACT, TORT, "
          "OR OTHERWISE, SHALL NOT EXCEED THE LESSER OF (A) FIVE HUNDRED DOLLARS ($500) "
          "OR (B) THE AMOUNT PAID BY CLIENT IN THE ONE (1) CALENDAR MONTH IMMEDIATELY "
          "PRECEDING THE EVENT GIVING RISE TO THE CLAIM.\n"
          "4.2 IN NO EVENT SHALL SERVICE PROVIDER BE LIABLE FOR LOSS OF DATA, LOSS OF "
          "PROFITS, BUSINESS INTERRUPTION, OR ANY INDIRECT, SPECIAL, OR CONSEQUENTIAL "
          "DAMAGES, EVEN IF SERVICE PROVIDER HAS BEEN ADVISED OF THE POSSIBILITY THEREOF.\n"
          "4.3 Client acknowledges that the fees charged under this Agreement reflect the "
          "allocation of risk set forth herein and that Service Provider would not enter "
          "into this Agreement on different terms.")

    write(pdf, "5. Indemnification",
          "5.1 Client shall defend, indemnify, and hold harmless Service Provider and its "
          "officers, directors, employees, agents, and successors ('Service Provider Indemnitees') "
          "from and against any and all claims, damages, losses, liabilities, judgments, "
          "fines, penalties, costs, and expenses (including reasonable attorneys' fees) "
          "arising out of or relating to: (a) Client's use of the Services; (b) any "
          "third-party claims related to the Client's systems, data, or business operations; "
          "(c) Client's breach of this Agreement; or (d) any negligence or wilful misconduct "
          "of Client or its personnel.\n"
          "5.2 Service Provider shall have no obligation to indemnify Client for any claims "
          "except those arising from Service Provider's gross negligence or wilful misconduct, "
          "and such indemnity shall be subject to the liability cap in Section 4.1.")

    write(pdf, "6. Data and Security",
          "6.1 Service Provider may access Client systems and data as reasonably necessary "
          "to perform the Services.\n"
          "6.2 Service Provider shall implement commercially reasonable administrative, "
          "technical, and physical safeguards designed to protect Client data from unauthorised "
          "access or disclosure.\n"
          "6.3 In the event of a security incident affecting Client data, Service Provider "
          "shall investigate and take reasonable remediation steps. Service Provider shall "
          "notify Client of any confirmed data breach involving Client's personal data within "
          "a commercially reasonable time after confirmation.\n"
          "6.4 Service Provider shall not be responsible for any loss of Client data arising "
          "from hardware failure, ransomware, or force majeure events.")

    write(pdf, "7. Warranties and Disclaimer",
          "7.1 Service Provider warrants that the Services will be performed in a "
          "professional and workmanlike manner consistent with generally accepted industry "
          "standards.\n"
          "7.2 EXCEPT AS EXPRESSLY SET FORTH IN SECTION 7.1, SERVICE PROVIDER MAKES NO "
          "WARRANTIES, EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION THE IMPLIED "
          "WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. SERVICE "
          "PROVIDER DOES NOT WARRANT THAT THE SERVICES WILL BE UNINTERRUPTED OR ERROR-FREE.")

    write(pdf, "8. Confidentiality",
          "8.1 Each party may disclose to the other certain proprietary or confidential "
          "information ('Confidential Information'). Each party agrees to protect the "
          "Confidential Information of the other party with at least the same degree of "
          "care used to protect its own confidential information.\n"
          "8.2 Client's Confidential Information includes its customer lists, financial data, "
          "and system configurations. Service Provider's Confidential Information includes "
          "its pricing, tools, and methodologies.")

    write(pdf, "9. Governing Law",
          "9.1 This Agreement shall be governed by the laws of the State of Texas without "
          "regard to its conflict of law provisions. Any disputes shall be resolved "
          "exclusively in the state or federal courts located in Dallas County, Texas, "
          "and each party irrevocably submits to the personal jurisdiction thereof.")

    write(pdf, "10. Entire Agreement",
          "10.1 This Agreement, together with all Schedules, constitutes the entire agreement "
          "between the parties with respect to its subject matter and supersedes all prior "
          "agreements, understandings, negotiations, and representations.\n"
          "10.2 Service Provider may amend this Agreement by providing 14 days' written "
          "notice to Client. Continued use of Services after such period constitutes acceptance.")

    pdf.save("smb_managed_it_services.pdf")


# ===========================================================================
# CONTRACT 3 — Healthcare / HIPAA
# Persona: Healthcare Compliance Officer
# Traps: BAA only upon request (not mandatory), 90-day breach notice (exceeds HIPAA),
#         PHI deletion within 180 days, subprocessors can change anytime,
#         vendor uses de-identified data for benchmarking and sale
# ===========================================================================

def make_hipaa_contract():
    pdf = ContractPDF(
        title="MedConnect EHR Integration Services Agreement",
        parties="Between MedConnect Systems, Inc. ('Vendor') and Healthcare Organization ('Client')\n"
                "Effective Date: February 1, 2025  |  Initial Term: 36 Months"
    )

    write(pdf, "1. Services",
          "1.1 Vendor shall provide EHR integration, HL7/FHIR data pipeline services, "
          "and patient data analytics as described in the Statement of Work ('SOW') "
          "attached as Exhibit A.\n"
          "1.2 Vendor may update or modify the Services provided that the core functionality "
          "described in Exhibit A is not materially diminished.")

    write(pdf, "2. Protected Health Information",
          "2.1 The parties acknowledge that in the course of providing the Services, Vendor "
          "may receive, create, maintain, or transmit Protected Health Information ('PHI') "
          "as defined under the Health Insurance Portability and Accountability Act of 1996 "
          "('HIPAA') and its implementing regulations.\n"
          "2.2 A Business Associate Agreement ('BAA') governing Vendor's handling of PHI "
          "is available upon written request by Client and shall, if executed, be incorporated "
          "into this Agreement by reference. Absent a fully executed BAA, Client represents "
          "and warrants that it will not transmit PHI to Vendor's systems.\n"
          "2.3 Vendor may process de-identified data (as defined under 45 C.F.R. S 164.514) "
          "derived from Client data for purposes including product improvement, performance "
          "benchmarking, and commercialisation of aggregate insights, without restriction "
          "and without further consent from Client.")

    write(pdf, "3. Subprocessors and Third-Party Access",
          "3.1 Vendor may engage third-party subprocessors to assist in delivering the "
          "Services. A current list of approved subprocessors is set forth in Exhibit C.\n"
          "3.2 Vendor reserves the right to add, remove, or replace subprocessors at any "
          "time upon providing Client with reasonable notice, which the parties agree shall "
          "mean no less than 10 calendar days' advance written notification.\n"
          "3.3 Vendor shall enter into written agreements with subprocessors containing "
          "data protection obligations no less protective than those in this Agreement. "
          "Client acknowledges that enforcing such obligations against subprocessors is "
          "Vendor's responsibility, and Client shall have no direct recourse against "
          "Vendor's subprocessors.")

    write(pdf, "4. Security Incident and Breach Notification",
          "4.1 Vendor shall maintain a written information security programme that includes "
          "administrative, technical, and physical safeguards appropriate to the size, "
          "complexity, and sensitivity of PHI processed.\n"
          "4.2 In the event Vendor discovers a Security Incident that constitutes a Breach "
          "as defined under HIPAA, Vendor shall notify Client in writing within ninety (90) "
          "calendar days of Vendor's confirmation of the Breach. Notification shall include, "
          "to the extent reasonably practicable: (a) a description of the Breach; (b) the "
          "types of PHI involved; (c) steps individuals may take to protect themselves; and "
          "(d) a brief description of Vendor's investigation and remediation steps.\n"
          "4.3 Vendor's liability for any Breach arising from a subprocessor's acts or "
          "omissions shall be limited to Vendor's contractual recovery from such subprocessor.")

    write(pdf, "5. Audit Rights",
          "5.1 Client shall have the right to conduct, or commission a qualified third party "
          "to conduct, no more than one (1) security audit of Vendor's relevant systems and "
          "controls per calendar year, subject to the following conditions: (a) Client must "
          "provide no less than 90 days' advance written notice; (b) the audit shall be "
          "conducted during normal business hours and must not unreasonably disrupt Vendor's "
          "operations; (c) audit costs shall be borne solely by Client; and (d) any audit "
          "report shall be treated as Vendor's Confidential Information.\n"
          "5.2 Vendor may, in lieu of a direct audit, provide Client with the results of "
          "a third-party security assessment (such as a SOC 2 Type I report) conducted "
          "within the preceding 18 months, at Vendor's sole discretion.")

    write(pdf, "6. Data Retention and Deletion",
          "6.1 Vendor shall retain Client data, including PHI, for the term of this Agreement "
          "and for a period of 180 days following expiration or termination ('Retention Period').\n"
          "6.2 Following the Retention Period, Vendor shall permanently delete or destroy "
          "all Client data in its possession, custody, or control, including copies held by "
          "subprocessors, within a commercially reasonable time.\n"
          "6.3 Vendor shall provide written certification of deletion within 30 days of "
          "completing deletion, upon Client's written request.\n"
          "6.4 De-identified data as described in Section 2.3 is not subject to any "
          "deletion obligation.")

    write(pdf, "7. Term and Termination",
          "7.1 This Agreement shall be effective as of the Effective Date and shall continue "
          "for the Initial Term of 36 months. It shall automatically renew for successive "
          "12-month periods unless either party provides 90 days' written notice of "
          "non-renewal.\n"
          "7.2 Client may terminate for Vendor's material breach upon 30 days' written "
          "notice if such breach is not cured within that period.\n"
          "7.3 Vendor may terminate for convenience upon 60 days' written notice.")

    write(pdf, "8. Limitation of Liability",
          "8.1 VENDOR'S AGGREGATE LIABILITY FOR ALL CLAIMS ARISING UNDER THIS AGREEMENT "
          "SHALL NOT EXCEED THE TOTAL FEES PAID BY CLIENT IN THE TWELVE (12) MONTHS "
          "PRECEDING THE CLAIM.\n"
          "8.2 NEITHER PARTY SHALL BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, "
          "CONSEQUENTIAL, OR PUNITIVE DAMAGES REGARDLESS OF THE THEORY OF LIABILITY.\n"
          "8.3 THE FOREGOING LIMITATIONS SHALL APPLY EVEN IF A PARTY HAS BEEN ADVISED "
          "OF THE POSSIBILITY OF SUCH DAMAGES AND SHALL APPLY TO ALL CLAIMS INCLUDING "
          "THOSE ARISING FROM HIPAA VIOLATIONS.")

    write(pdf, "9. Governing Law",
          "9.1 This Agreement shall be governed by the laws of the State of Minnesota. "
          "Any disputes shall be resolved by binding arbitration in Minneapolis, Minnesota, "
          "under the rules of the American Arbitration Association.")

    pdf.save("healthcare_medconnect_ehr.pdf")


# ===========================================================================
# CONTRACT 4 — Employment / NDA
# Persona: Employment Counsel Reviewer
# Traps: 2-year nationwide non-compete, IP captures personal-time work,
#         all-employees non-solicit, no garden leave pay, unlimited confidentiality scope
# ===========================================================================

def make_employment_contract():
    pdf = ContractPDF(
        title="Employment Agreement and Proprietary Information,\n"
              "Invention Assignment, and Non-Competition Agreement",
        parties="Between Nexaflow Technologies, Inc. ('Company') and Employee\n"
                "Role: Senior Software Engineer  |  Start Date: April 1, 2025"
    )

    write(pdf, "1. Position and Duties",
          "1.1 Employee is employed as Senior Software Engineer. Employee agrees to devote "
          "Employee's full business time, attention, and best efforts to the performance "
          "of Employee's duties and to the furtherance of the Company's interests.\n"
          "1.2 Employee shall not engage in any outside employment, consulting, or business "
          "activity without the prior written consent of the Company.")

    write(pdf, "2. Compensation and Benefits",
          "2.1 Base Salary: Employee shall receive an annual base salary as set forth in "
          "the offer letter, payable bi-weekly, subject to required withholdings.\n"
          "2.2 At-Will Employment: Employment is at-will and may be terminated by either "
          "party at any time, with or without cause or notice.")

    write(pdf, "3. Proprietary Information and Confidentiality",
          "3.1 'Proprietary Information' means any and all information, whether or not "
          "in written form, that is not generally known to the public and that relates "
          "to the business, technology, operations, finances, customers, or strategic plans "
          "of the Company or any affiliate, including but not limited to source code, "
          "algorithms, product roadmaps, customer lists, pricing, sales data, and any other "
          "information that Employee learns or develops in connection with Employee's "
          "employment. Employee acknowledges that Proprietary Information also includes "
          "any information Employee had access to, or knowledge of, as a result of skills, "
          "training, or knowledge acquired during employment, even if such information was "
          "not explicitly marked confidential.\n"
          "3.2 Employee agrees to hold all Proprietary Information in strict confidence and "
          "not to disclose or use it except as required in the performance of Employee's duties.\n"
          "3.3 This confidentiality obligation shall survive termination of employment "
          "for an indefinite period, or until the information enters the public domain "
          "through no act or omission of Employee.")

    write(pdf, "4. Invention Assignment",
          "4.1 Employee agrees to assign, and hereby assigns, to the Company all right, title, "
          "and interest in and to any and all inventions, original works of authorship, "
          "developments, concepts, improvements, designs, discoveries, software, code, "
          "algorithms, data models, and trade secrets, whether or not patentable or "
          "registrable ('Inventions'), that Employee makes, conceives, reduces to practice, "
          "or develops, either alone or jointly with others:\n"
          "  (a) during the period of Employee's employment with the Company; or\n"
          "  (b) using the Company's equipment, supplies, facilities, or Proprietary Information; or\n"
          "  (c) that relate to the Company's actual or demonstrably anticipated business, "
          "research, or development; or\n"
          "  (d) that result from work performed by Employee for the Company; or\n"
          "  (e) that relate to or arise from any skills, knowledge, or expertise acquired "
          "by Employee during employment, regardless of when or where such Invention is "
          "conceived or developed.\n"
          "4.2 Employee further waives all moral rights in all Inventions assigned hereunder "
          "to the fullest extent permitted by applicable law.\n"
          "4.3 Employee shall promptly disclose all Inventions to the Company in writing.")

    write(pdf, "5. Non-Competition",
          "5.1 During employment and for a period of two (2) years following the termination "
          "of Employee's employment for any reason, including termination by the Company "
          "without cause, Employee shall not, directly or indirectly, anywhere in the "
          "United States of America:\n"
          "  (a) engage in, own, manage, operate, control, be employed by, provide services "
          "to, participate in, or be connected with any business or enterprise that "
          "competes with, or is substantially similar to, any business in which the "
          "Company is engaged or in which the Company has taken material steps to engage "
          "during the 24 months preceding Employee's termination; or\n"
          "  (b) develop, design, or market any product or service that competes with any "
          "product or service offered or planned by the Company.\n"
          "5.2 Employee acknowledges that the geographic scope and duration of this "
          "restriction are reasonable given the national nature of the Company's business "
          "and Employee's access to Proprietary Information.\n"
          "5.3 No compensation or garden leave payment shall be payable by the Company to "
          "Employee in exchange for compliance with this Section 5.")

    write(pdf, "6. Non-Solicitation",
          "6.1 During employment and for twenty-four (24) months following termination, "
          "Employee shall not, directly or indirectly:\n"
          "  (a) solicit, recruit, induce, or encourage any employee, contractor, or "
          "consultant of the Company to terminate or reduce their relationship with "
          "the Company, regardless of whether Employee initiates such contact;\n"
          "  (b) solicit, divert, or take away, or attempt to solicit, divert, or take away, "
          "any customer, client, or prospective customer of the Company, regardless of "
          "whether Employee had direct dealings with such customer during employment.\n"
          "6.2 'Prospective customer' means any entity or individual with whom the Company "
          "had contact for the purpose of offering its products or services in the 24 months "
          "preceding Employee's termination.")

    write(pdf, "7. Remedies",
          "7.1 Employee acknowledges that any breach of Sections 3, 4, 5, or 6 would cause "
          "irreparable harm to the Company for which monetary damages would be inadequate. "
          "Accordingly, the Company shall be entitled to seek injunctive relief, specific "
          "performance, or other equitable relief without the requirement to post a bond "
          "or other security, in addition to all other available remedies.\n"
          "7.2 In the event of a breach, the restricted period shall be automatically "
          "extended by a period equal to the duration of the breach.")

    write(pdf, "8. Governing Law",
          "8.1 This Agreement shall be governed by the laws of the State of California. "
          "Employee consents to the exclusive jurisdiction of the state and federal courts "
          "in San Francisco County, California.")

    write(pdf, "9. Severability",
          "9.1 If any provision of this Agreement is found to be unenforceable, the "
          "remaining provisions shall continue in full force. Any unenforceable provision "
          "shall be modified to the minimum extent necessary to make it enforceable while "
          "preserving the parties' original intent.")

    pdf.save("employment_nexaflow_engineer.pdf")


# ===========================================================================
# CONTRACT 5 — Strict / Enterprise
# Persona: Conservative Enterprise Legal Counsel
# Traps: unlimited liability carve-outs for IP/breach, Cayman Islands governing law,
#         no customer termination for convenience, 90-day renewal notice,
#         unilateral vendor audit rights with 5 days notice, no customer assignment
# ===========================================================================

def make_enterprise_contract():
    pdf = ContractPDF(
        title="Enterprise Software License and Services Agreement",
        parties="Between Orbis Global Software Ltd. ('Licensor') and Enterprise Customer ('Licensee')\n"
                "Effective Date: January 15, 2025  |  Initial Term: 36 Months"
    )

    write(pdf, "1. Grant of License",
          "1.1 Subject to the terms of this Agreement and payment of applicable fees, "
          "Licensor grants Licensee a limited, non-exclusive, non-transferable, "
          "non-sublicensable licence to use the Orbis Enterprise Platform ('Software') "
          "solely for Licensee's internal business operations during the Term.\n"
          "1.2 All rights not expressly granted herein are reserved by Licensor. Licensee "
          "shall not: (a) reverse-engineer, decompile, or disassemble the Software; "
          "(b) sublicense or transfer access to any third party; (c) use the Software for "
          "any outsourcing, SaaS, or service bureau purpose without prior written consent.")

    write(pdf, "2. Fees and Payment",
          "2.1 Licensee shall pay the annual licence fees set forth in Order Form 1 ('Fees') "
          "in advance at the beginning of each term year.\n"
          "2.2 Licensor may adjust Fees for any renewal term upon 60 days' written notice, "
          "without limitation as to the amount of any increase.\n"
          "2.3 All Fees are non-refundable. Invoices are due net-30.\n"
          "2.4 Late payments accrue interest at 2% per month.")

    write(pdf, "3. Term and Renewal",
          "3.1 This Agreement commences on the Effective Date and shall continue for the "
          "Initial Term of thirty-six (36) months, and shall automatically renew for "
          "successive 24-month terms unless Licensee provides written notice of "
          "non-renewal no less than 90 days prior to the end of the then-current term.\n"
          "3.2 Licensee may terminate this Agreement solely upon Licensor's uncured "
          "material breach after 60 days written notice. Licensor shall have the right "
          "to determine in its sole discretion whether a breach has been cured.\n"
          "3.3 Licensor may terminate for convenience upon 30 days' notice to Licensee, "
          "in which case Licensor shall refund pre-paid fees for the unused portion of "
          "the then-current term as Licensee's sole remedy.")

    write(pdf, "4. Intellectual Property Indemnity",
          "4.1 Licensor shall defend, indemnify, and hold harmless Licensee from any "
          "third-party claim alleging that the Software, as delivered, infringes any "
          "patent, copyright, or trade secret, provided that Licensee: (a) promptly "
          "notifies Licensor of the claim; (b) grants Licensor sole control of the defence; "
          "and (c) provides reasonable cooperation.\n"
          "4.2 Licensee shall defend, indemnify, and hold harmless Licensor from any "
          "third-party claim arising out of or relating to: (a) Licensee's use or misuse "
          "of the Software; (b) any modification made by Licensee; (c) combination of the "
          "Software with third-party products; or (d) Licensee's data, content, or "
          "business practices. THIS INDEMNITY IS NOT SUBJECT TO THE LIABILITY CAP IN "
          "SECTION 5 AND IS UNLIMITED IN AMOUNT.")

    write(pdf, "5. Limitation of Liability",
          "5.1 EXCEPT AS SET FORTH IN SECTIONS 4.2 AND 6, LICENSOR'S TOTAL AGGREGATE "
          "LIABILITY TO LICENSEE FOR ANY CLAIMS ARISING UNDER OR RELATED TO THIS "
          "AGREEMENT SHALL NOT EXCEED THE TOTAL FEES PAID BY LICENSEE IN THE TWELVE "
          "(12) MONTHS IMMEDIATELY PRECEDING THE CLAIM.\n"
          "5.2 NEITHER PARTY SHALL BE LIABLE FOR INDIRECT, INCIDENTAL, CONSEQUENTIAL, "
          "SPECIAL, OR PUNITIVE DAMAGES.\n"
          "5.3 The following are expressly excluded from the limitation in Section 5.1 and "
          "shall expose Licensee to UNLIMITED LIABILITY: (a) breach of confidentiality "
          "obligations by Licensee; (b) misappropriation of Licensor's intellectual "
          "property; (c) Licensee's indemnification obligations under Section 4.2; "
          "and (d) Licensee's data processing obligations under the DPA.")

    write(pdf, "6. Data Protection",
          "6.1 The parties shall enter into Licensor's standard Data Processing Addendum "
          "('DPA') as a condition of processing personal data under this Agreement. "
          "The DPA is provided by Licensor and may be updated by Licensor from time to time "
          "to reflect changes in applicable law.\n"
          "6.2 In the event of a data breach involving Licensee's data, Licensor shall "
          "notify Licensee within 72 hours of confirmed discovery.\n"
          "6.3 Licensee's liability for any data breach caused by Licensee's failure to "
          "implement adequate security controls is not subject to the cap in Section 5.1.")

    write(pdf, "7. Audit Rights",
          "7.1 Licensor shall have the right to audit Licensee's use of the Software "
          "to verify compliance with this Agreement, including licence seat counts and "
          "use restrictions, upon not less than five (5) business days' prior written "
          "notice. Audits shall be conducted during business hours and no more than twice "
          "per calendar year.\n"
          "7.2 If an audit reveals underpayment of Fees, Licensee shall pay the shortfall "
          "plus interest at 2% per month plus Licensor's reasonable audit costs if the "
          "underpayment exceeds 5% of amounts due.")

    write(pdf, "8. Assignment and Change of Control",
          "8.1 Licensee may not assign or transfer this Agreement or any rights hereunder "
          "without the prior written consent of Licensor, which may be withheld in "
          "Licensor's sole discretion. Any purported assignment in violation of this "
          "Section shall be void.\n"
          "8.2 Licensor may freely assign this Agreement in connection with a merger, "
          "acquisition, reorganisation, or sale of all or substantially all of its assets "
          "without Licensee's consent.\n"
          "8.3 For purposes of this Agreement, a Change of Control of Licensee (meaning "
          "any transaction resulting in a change of more than 50% of Licensee's voting "
          "securities) shall be deemed an assignment requiring Licensor's prior written "
          "consent. Licensor may condition its consent upon renegotiation of Fees.")

    write(pdf, "9. Governing Law and Dispute Resolution",
          "9.1 This Agreement shall be governed exclusively by the laws of the Cayman "
          "Islands, without regard to conflict of law principles.\n"
          "9.2 All disputes arising out of or in connection with this Agreement shall be "
          "finally resolved by arbitration under the LCIA Rules, with the seat of "
          "arbitration in London, United Kingdom. The language of arbitration shall be "
          "English. The arbitral award shall be final and binding.\n"
          "9.3 Licensor may seek interim or emergency injunctive relief in any court of "
          "competent jurisdiction without waiving the right to arbitrate.")

    write(pdf, "10. Warranties and Disclaimer",
          "10.1 Licensor warrants that the Software will perform materially in accordance "
          "with the Documentation for 90 days from delivery ('Warranty Period'). "
          "Licensee's exclusive remedy for a warranty claim is Licensor's commercially "
          "reasonable effort to correct the defect, or if Licensor cannot do so within "
          "60 days, a refund of pre-paid fees for the remaining Warranty Period.\n"
          "10.2 EXCEPT AS SET FORTH IN SECTION 10.1, THE SOFTWARE IS PROVIDED 'AS IS' "
          "WITHOUT ANY WARRANTY.")

    write(pdf, "11. Miscellaneous",
          "11.1 This Agreement constitutes the entire agreement between the parties.\n"
          "11.2 Any amendment must be in writing and signed by both parties, except that "
          "Licensor may amend its standard DPA and acceptable use policy by posting "
          "updated versions on its website with 30 days' notice.")

    pdf.save("enterprise_orbis_software_license.pdf")


# ===========================================================================
# Run all generators
# ===========================================================================

if __name__ == "__main__":
    print(f"Generating sample contracts into ./{OUTPUT_DIR}/\n")
    make_saas_contract()
    make_smb_contract()
    make_hipaa_contract()
    make_employment_contract()
    make_enterprise_contract()
    print(f"\nDone. Upload any of these PDFs to ClauseSense and choose the matching playbook.")
    print("""
Recommended pairings:
  saas_cloudvault_pro.pdf           ->  SaaS / Software playbook
  smb_managed_it_services.pdf       ->  Standard SMB playbook
  healthcare_medconnect_ehr.pdf     ->  Healthcare / HIPAA playbook
  employment_nexaflow_engineer.pdf  ->  Employment / NDA playbook
  enterprise_orbis_software_license.pdf  ->  Strict / Enterprise playbook
""")
