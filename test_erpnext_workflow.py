import frappe
from frappe.utils import nowdate, flt

TEST_CONFIG = {
    "company": "Test Industrial Company",
    "abbr": "TIC",
    "currency": "INR",
    "warehouse": "Stores - TIC",
    "wip_warehouse": "Work In Progress - TIC",
    "fg_warehouse": "Finished Goods - TIC",
    "supplier": "Test Supplier",
    "customer": "Test Customer",
    "item_group": "Raw Material",
    "item_group_fg": "Finished Goods",
    "uom": "Nos"
}

class ERPNextAccountingWorkflowTest:
    def __init__(self):
        self.results = []
        self.test_docs = {}
        self.company = None
        self.cost_center = None
        
    def log(self, message, status="INFO"):
        timestamp = frappe.utils.now().split(".")[0].split(" ")[1]
        status_icon = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}.get(status, "•")
        print(f"[{timestamp}] {status_icon} {message}")
        self.results.append({"time": timestamp, "message": message, "status": status})
    
    def setup_test_environment(self):
        self.log("=== PHASE 1: SETUP & CONFIGURATION ===", "INFO")
        try:
            if not frappe.db.exists("Company", TEST_CONFIG["company"]):
                company = frappe.get_doc({
                    "doctype": "Company",
                    "company_name": TEST_CONFIG["company"],
                    "abbr": TEST_CONFIG["abbr"],
                    "default_currency": TEST_CONFIG["currency"],
                    "country": "India",
                    "enable_perpetual_inventory": 1,
                    "create_chart_of_accounts_based_on": "Standard Chart of Accounts",
                    "chart_of_accounts": "Standard"
                })
                company.insert()
                frappe.db.commit()
                self.company = company.name
                self.log(f"Created Company: {company.name}", "SUCCESS")
            else:
                self.company = TEST_CONFIG["company"]
                self.log(f"Using existing Company: {self.company}", "WARNING")
            
            self.cost_center = frappe.db.get_value("Cost Center", 
                {"company": self.company, "is_group": 0}, "name")
            self.log(f"Cost Center: {self.cost_center}", "INFO")
            
            warehouses = [
                (TEST_CONFIG["warehouse"], "Stores"),
                (TEST_CONFIG["wip_warehouse"], "Work In Progress"),
                (TEST_CONFIG["fg_warehouse"], "Finished Goods")
            ]
            
            for wh_name, wh_type in warehouses:
                if not frappe.db.exists("Warehouse", wh_name):
                    wh = frappe.get_doc({
                        "doctype": "Warehouse",
                        "warehouse_name": wh_type,
                        "company": self.company
                    })
                    wh.insert()
                    frappe.db.commit()
                    self.log(f"Created Warehouse: {wh.name}", "SUCCESS")
            
            if not frappe.db.exists("Supplier", TEST_CONFIG["supplier"]):
                sup = frappe.get_doc({
                    "doctype": "Supplier",
                    "supplier_name": TEST_CONFIG["supplier"],
                    "supplier_type": "Company",
                    "company": self.company
                })
                sup.insert()
                frappe.db.commit()
                self.log(f"Created Supplier: {sup.name}", "SUCCESS")
            
            if not frappe.db.exists("Customer", TEST_CONFIG["customer"]):
                cust = frappe.get_doc({
                    "doctype": "Customer",
                    "customer_name": TEST_CONFIG["customer"],
                    "customer_type": "Company",
                    "company": self.company
                })
                cust.insert()
                frappe.db.commit()
                self.log(f"Created Customer: {cust.name}", "SUCCESS")
            
            return True
        except Exception as e:
            self.log(f"Setup Error: {str(e)}", "ERROR")
            return False

    def test_purchase_workflow(self):
        self.log("\n=== PHASE 2: PURCHASE WORKFLOW TEST ===", "INFO")
        try:
            item_code = "TEST-RM-001"
            if not frappe.db.exists("Item", item_code):
                item = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": "Test Raw Material 001",
                    "item_group": TEST_CONFIG["item_group"],
                    "stock_uom": TEST_CONFIG["uom"],
                    "is_stock_item": 1,
                    "is_purchase_item": 1,
                    "standard_rate": 100,
                    "valuation_method": "FIFO"
                })
                item.insert()
                frappe.db.commit()
                self.test_docs["item_rm"] = item.name
                self.log(f"Created Item: {item.name}", "SUCCESS")
            
            po = frappe.get_doc({
                "doctype": "Purchase Order",
                "supplier": TEST_CONFIG["supplier"],
                "company": self.company,
                "transaction_date": nowdate(),
                "items": [{
                    "item_code": item_code,
                    "qty": 100,
                    "rate": 100,
                    "warehouse": TEST_CONFIG["warehouse"],
                    "schedule_date": nowdate()
                }]
            })
            po.insert()
            po.submit()
            frappe.db.commit()
            self.test_docs["po"] = po.name
            self.log(f"Created PO: {po.name} | Total: {po.total}", "SUCCESS")
            
            gl_entries = frappe.db.get_all("GL Entry", 
                filters={"voucher_type": "Purchase Order", "voucher_no": po.name})
            if len(gl_entries) == 0:
                self.log("✓ PO creates no GL entries (correct - commitment only)", "SUCCESS")
            else:
                self.log("✗ PO should not create GL entries!", "ERROR")
            
            pr = frappe.get_doc({
                "doctype": "Purchase Receipt",
                "supplier": TEST_CONFIG["supplier"],
                "company": self.company,
                "posting_date": nowdate(),
                "items": [{
                    "item_code": item_code,
                    "qty": 100,
                    "rate": 100,
                    "warehouse": TEST_CONFIG["warehouse"]
                }]
            })
            pr.insert()
            pr.submit()
            frappe.db.commit()
            self.test_docs["pr"] = pr.name
            self.log(f"Created PR: {pr.name}", "SUCCESS")
            
            gl_entries = frappe.get_all("GL Entry", 
                filters={"voucher_type": "Purchase Receipt", "voucher_no": pr.name},
                fields=["account", "debit", "credit"])
            
            inventory_dr = sum([g.debit for g in gl_entries if "Inventory" in g.account])
            rbnb_cr = sum([g.credit for g in gl_entries if "Stock Received But Not Billed" in g.account])
            
            if inventory_dr == 10000 and rbnb_cr == 10000:
                self.log(f"✓ PR GL Entries correct: Inventory Dr {inventory_dr}, RBNB Cr {rbnb_cr}", "SUCCESS")
            else:
                self.log(f"✗ PR GL mismatch: Inventory Dr {inventory_dr}, RBNB Cr {rbnb_cr}", "ERROR")
            
            pi = frappe.get_doc({
                "doctype": "Purchase Invoice",
                "supplier": TEST_CONFIG["supplier"],
                "company": self.company,
                "posting_date": nowdate(),
                "items": [{
                    "item_code": item_code,
                    "qty": 100,
                    "rate": 100,
                    "warehouse": TEST_CONFIG["warehouse"],
                    "purchase_receipt": pr.name
                }]
            })
            pi.insert()
            pi.submit()
            frappe.db.commit()
            self.test_docs["pi"] = pi.name
            self.log(f"Created PI: {pi.name}", "SUCCESS")
            
            gl_entries = frappe.get_all("GL Entry", 
                filters={"voucher_type": "Purchase Invoice", "voucher_no": pi.name},
                fields=["account", "debit", "credit"])
            
            rbnb_dr = sum([g.debit for g in gl_entries if "Stock Received But Not Billed" in g.account])
            payable_cr = sum([g.credit for g in gl_entries if "Creditors" in g.account])
            
            if rbnb_dr == 10000 and payable_cr == 10000:
                self.log(f"✓ PI GL Entries correct: RBNB Dr {rbnb_dr}, Payable Cr {payable_cr}", "SUCCESS")
            else:
                self.log(f"✗ PI GL mismatch: RBNB Dr {rbnb_dr}, Payable Cr {payable_cr}", "ERROR")
            
            pe = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": "Pay",
                "company": self.company,
                "posting_date": nowdate(),
                "party_type": "Supplier",
                "party": TEST_CONFIG["supplier"],
                "paid_from": self.get_bank_account(),
                "paid_to": self.get_party_account("Supplier", TEST_CONFIG["supplier"]),
                "paid_amount": 10000,
                "received_amount": 10000,
                "references": [{
                    "reference_doctype": "Purchase Invoice",
                    "reference_name": pi.name,
                    "allocated_amount": 10000
                }]
            })
            pe.insert()
            pe.submit()
            frappe.db.commit()
            self.test_docs["payment"] = pe.name
            self.log(f"Created Payment: {pe.name}", "SUCCESS")
            
            gl_entries = frappe.get_all("GL Entry", 
                filters={"voucher_type": "Payment Entry", "voucher_no": pe.name},
                fields=["account", "debit", "credit"])
            
            payable_dr = sum([g.debit for g in gl_entries if "Creditors" in g.account])
            bank_cr = sum([g.credit for g in gl_entries if "Bank" in g.account])
            
            if payable_dr == 10000 and bank_cr == 10000:
                self.log(f"✓ Payment GL Entries correct: Payable Dr {payable_dr}, Bank Cr {bank_cr}", "SUCCESS")
            else:
                self.log(f"✗ Payment GL mismatch: Payable Dr {payable_dr}, Bank Cr {bank_cr}", "ERROR")
            
            sup_balance = frappe.db.get_value("GL Entry", 
                {"party": TEST_CONFIG["supplier"], "is_cancelled": 0}, 
                "sum(debit-credit)")
            self.log(f"Supplier Balance after payment: {sup_balance or 0}", "INFO")
            
            return True
        except Exception as e:
            self.log(f"Purchase Workflow Error: {str(e)}", "ERROR")
            frappe.log_error(frappe.get_traceback(), "Purchase Workflow Test")
            return False

    def get_bank_account(self):
        return frappe.db.get_value("Account", 
            {"account_type": "Bank", "company": self.company, "is_group": 0}, "name")
    
    def get_party_account(self, party_type, party):
        from erpnext.accounts.party import get_party_account
        return get_party_account(party_type, party, self.company)
    
    def generate_test_report(self):
        print("\n" + "="*80)
        print("ERPNext Accounting Workflow Test Report".center(80))
        print("="*80)
        success_count = sum(1 for r in self.results if r["status"] == "SUCCESS")
        error_count = sum(1 for r in self.results if r["status"] == "ERROR")
        print(f"\nTotal Tests: {len(self.results)}")
        print(f"✅ Success: {success_count}")
        print(f"❌ Errors: {error_count}")
        print(f"⚠️ Warnings: {len(self.results) - success_count - error_count}")
        print("\nDetailed Log:")
        for r in self.results:
            icon = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}.get(r["status"], "•")
            print(f"{icon} [{r['time']}] {r['message']}")
        print("\n" + "="*80)
        return success_count, error_count

def run_test():
    print("Starting ERPNext Industrial Accounting Workflow Test...")
    print(f"Site: {frappe.local.site}")
    print(f"Time: {frappe.utils.now()}")
    print("-" * 80)
    tester = ERPNextAccountingWorkflowTest()
    phases = [
        ("Setup", tester.setup_test_environment),
        ("Purchase Workflow", tester.test_purchase_workflow),
    ]
    completed = 0
    for name, phase_func in phases:
        try:
            if phase_func():
                completed += 1
            else:
                print(f"\n⚠️ Phase \'{name}\' failed but continuing...")
        except Exception as e:
            print(f"\n❌ Critical error in {name}: {str(e)}")
            frappe.log_error(frappe.get_traceback(), f"Test Phase Error: {name}")
    success, errors = tester.generate_test_report()
    print(f"\n{'='*80}")
    print(f"Test Execution Complete: {completed}/{len(phases)} phases successful")
    if errors == 0:
        print("🎉 All accounting workflows verified successfully!")
    else:
        print("⚠️ Review errors above for workflow issues")
    print(f"{'='*80}\n")
    return tester.results
