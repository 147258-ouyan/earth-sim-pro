# create_test_excel.py
import openpyxl

# 就在当前文件夹生成，不折腾目录
wb1 = openpyxl.Workbook()
ws1 = wb1.active
ws1.append(["商品", "销量"])
ws1.append(["A", 100])
ws1.append(["B", 200])
wb1.save("销售数据.xlsx")

wb2 = openpyxl.Workbook()
ws2 = wb2.active
ws2.append(["商品", "库存"])
ws2.append(["A", 50])
ws2.append(["B", 80])
wb2.save("库存表.xlsx")

print("已在当前文件夹生成 销售数据.xlsx 和 库存表.xlsx")
input("按回车键退出...")