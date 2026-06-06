/************* Object: StpredProcedure [dbo].[usp_ComplexProcedureName]   script date: yyyy/mm/dd ********************/
if exists (select * from sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[usp_ComplexProcedureName]') AND type IN (N'P', N'PC'))
	DROP procedure [dbo].[usp_ComplexProcedureName]
go

/*************************************************************************************
* sx knd skjxcndkcnxkjdncxkjsdn
* sx knd skjxcndkcnxkjdncxkjsdn
* sx knd skjxcndkcnxkjdncxkjsdn
* sx knd skjxcndkcnxkjdncxkjsdn
* sx knd skjxcndkcnxkjdncxkjsdn
* *****************************************************
* date modified: yyyy/mm/dd
* date                   programmer                      description
* 2026/06/02           Deepraj Adhikary                Initial release
* 2026/06/02           Deepraj Adhikary                Initial release
* 2026/06/02           Deepraj Adhikary                Initial release
*************************************************************************************/
create procedure [dbo].[usp_ComplexProcedureName]
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int,
	@field1 int
as

-- comment here

if isnull(field1, '') = '' or isnull(field2, '') not in ('A','B','C')
begin
	raiserror('bjhcbkjdbckhdfbkcjfd') with seterror
	return @@error
end

if isnull(@fiend, '') <> '' and isnull(@fld2, '') not in ('A','B')
begin
	if exists(
        select 'true' 
        from table1 a 
        inner join table2 b 
        on a.id = b.id 
        where a.fld1 = @fld1
        and b.fld2 = @fld2
    )
	begin
		raiserror('jshdcbjsdhc') with seterror
		return @@error
	end
end

if isnull(@fiend, '') <> '' and isnull(@fld2, '') not in ('A','B')
begin
	if exists(
		select 'true' 
		from table1 a 
		inner join table2 b 
		on a.id = b.id 
		where a.fld1 = @fld1
		and b.fld2 = @fld2
	)
	begin
		raiserror('jshdcbjsdhc') with seterror
		return @@error
	end
end


if isnull(@fld2, '') not in ('A','B')
begin
	declare @flda1 int
    declare @flda2 int
    select @flda1 = fld1, @flda2 = fld2 from dbo.proc_name1 (fld1, fld2, fld3, 'a') where id = @fld1
	if @flda1 > 0
    begin
		raiserror('jshdcbjsdhc') with seterror
		return @@error
	end
end

insert into table1 (fld1, fld2) values (@fld1, @fld2)

if @@rowcount = 0 and @@error <> 0
    goto error_label


insert into table2 (fld1, fld2) values (@fld1, @fld2)

if @@rowcount = 0 and @@error <> 0
    goto error_label

exec dbo.proc_name2
    @fld1 = @fld1,
    @fld2 = @fld2,
    @fld3 = @fld3,
    @fld4 = @fld4,
    @fld5 = @fld5,
    @fld6 = @fld6,
    @fld7 = @fld7

insert into table3 (fld1, fld2) values (@fld1, @fld2)

set @fldx1 = scope_identity()
declare @fldx2 int
select @fldx2 = fld2 from table3 where id = @fldx1
if @fldx2 > 0
begin
	insert into table4 (fld1, fld2) values (@fld1, @fld2)
    if @@rowcount = 0 and @@error <> 0
        goto error_label
end

error_label:
    raiserror('jshdcbjsdhc') with seterror
    return @@error
