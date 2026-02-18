import frappe
from frappe.utils import nowdate

def run_test():
    print("="*60)
    print("ERPNext Accounting Workflow Test")
    print("="*60)
    
    # Setup
    company = "Test Company"
    if not frappe.db.exists("Company", company):
        c = frappe.new_doc("Company")
        c.company_name = company
        c.abbr = "TC"
        c.default_currency = "INR"
        c.country = "India"
        c.enable_perpetual_inventory = 1
        c.insert()
        frappe.db.commit()
        print(f"✓ Created Company: {company}")
    else:
        print(f"✓ Using Company: {company}")
    
    # Create Supplier
    supplier = "Test Supplier"
    if not frappe.db.exists("Supplier", supplier):
        s = frappe.new_doc("Supplier")
        s.supplier_name = supplier
        s.insert()
        frappe.db.commit()
        print(f"✓ Created Supplier: {supplier}")
    
    # Create Item
    item = "TEST-ITEM-001"
    if not frappe.db.exists("Item", item):
        i = frappe.new_doc("Item")
        i.item_code = item
        i.item_name = "Test Item"
        i.item_group = "Products"
        i.is_stock_item = 1
        i.insert()
        frappe.db.commit()
        print(f"✓ Created Item: {item}")
    
    # Purchase Order
    po = frappe.new_doc("Purchase Order")
    po.supplier = supplier
    po.company = company
    po.transaction_date = nowdate()
    po.append("items", {
        "item_code": item,
        "qty": 10,
        "rate": 100,
        "warehouse": "Stores - TC",
        "schedule_date": nowdate()
    })
    po.insert()
    po.submit()
    frappe.db.commit()
    print(f"✓ Created PO: {po.name}")
    
    # Check GL Entries for PO (should be none)
    gl_count = frappe.db.count("GL Entry", {"voucher_type": "Purchase Order", "voucher_no": po.name})
    print(f"✓ PO GL Entries: {gl_count} (should be 0)")
    
    # Purchase Receipt
    pr = frappe.new_doc("Purchase Receipt")
    pr.supplier = supplier
    pr.company = company
    pr.posting_date = nowdate()
    pr.append("items", {
        "item_code": item,
        "qty": 10,
        "rate": 100,
        "warehouse": "Stores - TC"
    })
    pr.insert()
    pr.submit()
    frappe.db.commit()
    print(f"✓ Created PR: {pr.name}")
    
    # Check GL Entries for PR
    gl = frappe.get_all("GL Entry", 
        filters={"voucher_type": "Purchase Receipt", "voucher_no": pr.name},
        fields=["account", "debit", "credit"])
    print(f"✓ PR GL Entries: {len(gl)}")
    for entry in gl:
        print(f"   {entry.account}: Dr {entry.debit} Cr {entry.credit}")
    
    print("="*60)
    print("Test Complete!")
    print("="*60)
